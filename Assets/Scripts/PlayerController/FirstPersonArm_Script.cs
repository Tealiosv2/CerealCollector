using System;
using System.Collections;
using UnityEngine;

// First-person placeholder arm (plain untextured blocks) with a procedural
// pick-up animation: reach forward/down, close the hand, lift, return to rest.
//
// Sits under the player's camera. BuildArm() creates the joint hierarchy
//   Shoulder -> UpperArm, Elbow -> Forearm, Wrist -> Palm, Fingers
// so joints can be rotated independently. The animation is a short list of
// keyframed poses blended with smoothstep, so it needs no Animator/clips.
//
// Driven by PlayerPickup_Script (E while looking at a collectible).
// Hooks for the next step (moving the actual item):
//   OnGrab            - fired the moment the fingers close
//   OnPickupFinished  - fired when the arm is back at rest
public class FirstPersonArm_Script : MonoBehaviour
{
    [Header("Animation")]
    public float pickupDuration = 3.3f;   // reach, grab, raise, inspect, lower
    [Range(0f, 1f)] public float grabMoment = 0.20f;   // normalized time the hand closes

    [Header("Joints (created by BuildArm)")]
    public Transform shoulder;
    public Transform elbow;
    public Transform wrist;
    public Transform fingers;       // first finger segment (bends at the knuckles)
    public Transform fingerTips;    // second segment (bends halfway along); only with the hand model

    [Header("Hand")]
    [Tooltip("Low-poly hand model (FP_Hand.fbx: palm root with FP_Hand_Fingers > FP_Hand_FingerTips and FP_Hand_Thumb). "
           + "When set, it replaces the placeholder hand blocks at the wrist.")]
    public GameObject handModel;
    [Tooltip("Curl axis in the finger pieces' local space and its sign (curl toward the palm).")]
    public Vector3 curlAxis = Vector3.right;
    public float knuckleBend = 15f;     // degrees at full curl: fingers stay fairly flat along the box side...

    public float middleBend = 85f;      // ...and hook around its far edge at the middle joint

    [Header("Look")]
    public Material armMaterial;
    public Color armColor = new Color(0.55f, 0.50f, 0.48f);

    public event Action OnGrab;
    public event Action OnPickupFinished;
    public bool IsBusy { get; private set; }

    // ─── Poses ───────────────────────────────────────────────────────────────
    [Serializable]
    public struct ArmPose
    {
        public Vector3 shoulderPos;     // shoulder position in camera space
        public Vector3 shoulderEuler;   // x: pitch down, y: swing toward centre
        public float elbowBend;         // degrees, lifts the forearm
        public Vector3 wristEuler;
        public float fingerCurl;        // 0 open, 1 closed fist
        public float forearmRoll;       // degrees about the forearm's own axis (inspect turns happen here, not at the wrist)

        public static ArmPose Lerp(ArmPose a, ArmPose b, float t)
        {
            return new ArmPose
            {
                shoulderPos = Vector3.Lerp(a.shoulderPos, b.shoulderPos, t),
                shoulderEuler = Quaternion.Slerp(Quaternion.Euler(a.shoulderEuler), Quaternion.Euler(b.shoulderEuler), t).eulerAngles,
                elbowBend = Mathf.Lerp(a.elbowBend, b.elbowBend, t),
                wristEuler = Quaternion.Slerp(Quaternion.Euler(a.wristEuler), Quaternion.Euler(b.wristEuler), t).eulerAngles,
                fingerCurl = Mathf.Lerp(a.fingerCurl, b.fingerCurl, t),
                forearmRoll = Mathf.Lerp(a.forearmRoll, b.forearmRoll, t),   // plain lerp: the turn direction is explicit
            };
        }
    }

    // At rest the arm is fully below the view (and its blocks are hidden too).
    public ArmPose idlePose = new ArmPose
    {
        shoulderPos = new Vector3(0.60f, -1.55f, -0.20f),
        shoulderEuler = new Vector3(60f, -5f, 0f),
        elbowBend = 20f,
        wristEuler = new Vector3(0f, 0f, 0f),
        fingerCurl = 0.25f,
    };
    // Reaching forward and down toward the box, hand open, forearm starting to
    // turn so the hand meets the box's side.
    public ArmPose reachPose = new ArmPose
    {
        shoulderPos = new Vector3(0.45f, -0.55f, 0.15f),
        shoulderEuler = new Vector3(6f, -22f, 0f),
        elbowBend = 4f,
        wristEuler = new Vector3(12f, 0f, 0f),
        fingerCurl = 0.0f,
        forearmRoll = -40f,
    };
    // Hand on the side of the box (palm on its side panel, fingers up along it).
    public ArmPose grabPose = new ArmPose
    {
        shoulderPos = new Vector3(0.45f, -0.57f, 0.15f),
        shoulderEuler = new Vector3(8f, -22f, 0f),
        elbowBend = 6f,
        wristEuler = new Vector3(10f, 0f, 0f),
        fingerCurl = 0.15f,
        forearmRoll = -90f,
    };
    // Brought up in front of the view, forearm nearly upright: the front faces the player.
    public ArmPose liftPose = new ArmPose
    {
        shoulderPos = new Vector3(0.55f, -1.02f, 0.20f),
        shoulderEuler = new Vector3(12f, -20f, 0f),
        elbowBend = 95f,
        wristEuler = new Vector3(0f, 0f, 0f),
        fingerCurl = 0.15f,
        forearmRoll = -90f,
    };
    // Inspect, like a weapon inspect in CS / COD: the hand keeps its grip and
    // the FOREARM turns. First a look at the front...
    public ArmPose inspectPoseA = new ArmPose
    {
        shoulderPos = new Vector3(0.55f, -1.00f, 0.28f),
        shoulderEuler = new Vector3(10f, -22f, 0f),
        elbowBend = 100f,
        wristEuler = new Vector3(-5f, 0f, 0f),
        fingerCurl = 0.15f,
        forearmRoll = -95f,
    };
    // ...then the forearm rolls ~180 degrees to show the back (the arm shifts
    // left to keep the box near the centre as it swings across)...
    public ArmPose inspectPoseB = new ArmPose
    {
        shoulderPos = new Vector3(0.12f, -1.00f, 0.28f),
        shoulderEuler = new Vector3(10f, -8f, 0f),
        elbowBend = 100f,
        wristEuler = new Vector3(-5f, 0f, 0f),
        fingerCurl = 0.15f,
        forearmRoll = 85f,
    };
    // ...and a small settle on the back before lowering.
    public ArmPose inspectPoseC = new ArmPose
    {
        shoulderPos = new Vector3(0.12f, -1.00f, 0.28f),
        shoulderEuler = new Vector3(8f, -6f, 0f),
        elbowBend = 98f,
        wristEuler = new Vector3(-8f, 0f, 0f),
        fingerCurl = 0.15f,
        forearmRoll = 95f,
    };

    // ─── Lifecycle ───────────────────────────────────────────────────────────
    void Awake()
    {
        if (shoulder == null) BuildArm();
        ApplyPose(idlePose);
        SetVisible(false);
    }

    // The arm only exists on screen while it is animating.
    public void SetVisible(bool visible)
    {
        foreach (var r in GetComponentsInChildren<Renderer>(true)) r.enabled = visible;
    }

    public void PlayPickup()
    {
        if (!IsBusy && isActiveAndEnabled) StartCoroutine(PickupRoutine());
    }

    IEnumerator PickupRoutine()
    {
        IsBusy = true;
        SetVisible(true);
        bool grabbed = false;
        float t = 0f;
        while (t < 1f)
        {
            t = Mathf.Min(1f, t + Time.deltaTime / pickupDuration);
            SampleAt(t);
            if (!grabbed && t >= grabMoment)
            {
                grabbed = true;
                OnGrab?.Invoke();
            }
            yield return null;
        }
        IsBusy = false;
        SetVisible(false);
        OnPickupFinished?.Invoke();
    }

    // ─── Animation ───────────────────────────────────────────────────────────
    // Keyframes over normalized time:
    // rest -> reach -> grab -> lift -> inspect (turn, turn back, settle) -> lift -> rest.
    public void SampleAt(float t)
    {
        float[] times = { 0f, 0.14f, grabMoment, 0.30f, 0.42f, 0.60f, 0.76f, 0.88f, 1f };
        ArmPose[] poses = { idlePose, reachPose, grabPose, liftPose, inspectPoseA, inspectPoseB, inspectPoseC, liftPose, idlePose };
        for (int i = 0; i < times.Length - 1; i++)
        {
            if (t <= times[i + 1] || i == times.Length - 2)
            {
                float k = Mathf.InverseLerp(times[i], times[i + 1], t);
                k = k * k * (3f - 2f * k);                      // smoothstep ease in/out
                ApplyPose(ArmPose.Lerp(poses[i], poses[i + 1], k));
                return;
            }
        }
    }

    public void ApplyPose(ArmPose p)
    {
        if (shoulder == null) return;
        shoulder.localPosition = p.shoulderPos;
        shoulder.localRotation = Quaternion.Euler(p.shoulderEuler);
        // Bend at the elbow, then roll the forearm about its own length.
        elbow.localRotation = Quaternion.Euler(-p.elbowBend, 0f, 0f) * Quaternion.AngleAxis(p.forearmRoll, Vector3.forward);
        wrist.localRotation = Quaternion.Euler(p.wristEuler);
        if (fingerTips != null)
        {
            // Hand model: two bends (knuckles, then halfway along the fingers).
            fingers.localRotation = Quaternion.AngleAxis(p.fingerCurl * knuckleBend, curlAxis);
            fingerTips.localRotation = Quaternion.AngleAxis(p.fingerCurl * middleBend, curlAxis);
        }
        else
        {
            fingers.localRotation = Quaternion.Euler(p.fingerCurl * 95f, 0f, 0f);
        }
    }

    // ─── Construction ────────────────────────────────────────────────────────
    // Plain blocks along +Z from each joint. Sized for the house's ~3x scale.
    [ContextMenu("Rebuild Arm")]
    public void BuildArm()
    {
        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            var c = transform.GetChild(i).gameObject;
            if (Application.isPlaying) Destroy(c); else DestroyImmediate(c);
        }

        if (armMaterial == null)
        {
            armMaterial = new Material(Shader.Find("Standard")) { color = armColor };
        }

        shoulder = Joint("Shoulder", transform, Vector3.zero);
        elbow = Joint("Elbow", shoulder, new Vector3(0f, 0f, 0.78f));
        wrist = Joint("Wrist", elbow, new Vector3(0f, 0f, 0.72f));

        if (handModel != null)
        {
            // Low-poly skin arm + hand (FP_Hand.fbx). Each piece pivots at its joint
            // and its import rotation already points it along +Z (palm down), so it
            // is simply moved onto that joint: upper arm -> shoulder, forearm ->
            // elbow, palm (with fingers and thumb) -> wrist.
            var model = Instantiate(handModel);
            Attach(FindDeep(model.transform, "FP_Arm_Upper"), shoulder);
            Attach(FindDeep(model.transform, "FP_Arm_Fore"), elbow);
            var palm = FindDeep(model.transform, "FP_Hand_Palm") ?? model.transform;
            Attach(palm, wrist);
            if (palm != model.transform)
            {
                if (Application.isPlaying) Destroy(model); else DestroyImmediate(model);
            }
            fingers = FindDeep(wrist, "FP_Hand_Fingers");
            fingerTips = FindDeep(wrist, "FP_Hand_FingerTips");
            foreach (var r in GetComponentsInChildren<MeshRenderer>(true)) SetupRenderer(r);
            return;
        }

        Block("UpperArm", shoulder, new Vector3(0.22f, 0.22f, 0.78f), new Vector3(0f, 0f, 0.39f));
        Block("Forearm", elbow, new Vector3(0.19f, 0.18f, 0.72f), new Vector3(0f, 0f, 0.36f));
        Block("Palm", wrist, new Vector3(0.26f, 0.09f, 0.24f), new Vector3(0f, 0f, 0.12f));
        Block("Thumb", wrist, new Vector3(0.07f, 0.07f, 0.16f), new Vector3(-0.15f, -0.02f, 0.10f));
        fingers = Joint("Fingers", wrist, new Vector3(0f, 0f, 0.24f));
        fingerTips = null;
        Block("FingerBlock", fingers, new Vector3(0.25f, 0.07f, 0.20f), new Vector3(0f, 0f, 0.10f));
    }

    static void Attach(Transform piece, Transform joint)
    {
        if (piece == null) return;
        Quaternion importRotation = piece.localRotation;   // axis conversion from the FBX
        piece.SetParent(joint, false);
        piece.localPosition = Vector3.zero;
        piece.localRotation = importRotation;
        piece.localScale = Vector3.one;
    }

    static Transform FindDeep(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform c in root)
        {
            var hit = FindDeep(c, name);
            if (hit != null) return hit;
        }
        return null;
    }

    // Lit like the rest of the world: receives shadows (so the house blocks the
    // realtime sun indoors) and uses light probes when the scene has them.
    // It does not cast shadows, so it never darkens the view.
    static void SetupRenderer(Renderer r)
    {
        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        r.receiveShadows = true;
        r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.BlendProbes;
    }

    static Transform Joint(string name, Transform parent, Vector3 localPos)
    {
        var t = new GameObject(name).transform;
        t.SetParent(parent, false);
        t.localPosition = localPos;
        return t;
    }

    void Block(string name, Transform parent, Vector3 size, Vector3 center)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
        go.name = name;
        var col = go.GetComponent<Collider>();
        if (Application.isPlaying) Destroy(col); else DestroyImmediate(col);   // never blocks the player
        go.transform.SetParent(parent, false);
        go.transform.localPosition = center;
        go.transform.localScale = size;
        var r = go.GetComponent<MeshRenderer>();
        r.sharedMaterial = armMaterial;
        SetupRenderer(r);
    }
}
