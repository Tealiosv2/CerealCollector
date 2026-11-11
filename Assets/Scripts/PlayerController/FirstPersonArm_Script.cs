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
    public float pickupDuration = 2.2f;   // reach, grab, lift, pull in, lower
    [Range(0f, 1f)] public float grabMoment = 0.28f;   // normalized time the hand closes

    [Header("Joints (created by BuildArm)")]
    public Transform shoulder;
    public Transform elbow;
    public Transform wrist;
    public Transform fingers;       // first finger segment (bends at the knuckles)
    public Transform fingerTips;    // second segment (bends halfway along); only with the hand model
    public Transform thumb;         // thumb piece; only with the hand model

    [Header("Hand")]
    [Tooltip("Low-poly hand model (FP_Hand.fbx: palm root with FP_Hand_Fingers > FP_Hand_FingerTips and FP_Hand_Thumb). "
           + "When set, it replaces the placeholder hand blocks at the wrist.")]
    public GameObject handModel;
    [Tooltip("Curl axis in the finger pieces' local space and its sign (curl toward the palm).")]
    public Vector3 curlAxis = Vector3.right;
    public float knuckleBend = 80f;     // degrees at full curl: fingers wrap around the box's back edge at the knuckles...

    public float middleBend = 25f;      // ...and press onto the back face
    [Tooltip("Where the thumb points when gripping, in wrist space (fingers +Z, palm -Y, thumb side -X): "
           + "up the front of the box and slightly into it.")]
    public Vector3 thumbGripDirection = new Vector3(-0.62f, -0.45f, 0.60f);
    Quaternion thumbRest = Quaternion.identity, thumbGrip = Quaternion.identity;

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
        public float thumbCurl;         // 0 rest, 1 thumb pressed on the front of the box

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
                thumbCurl = Mathf.Lerp(a.thumbCurl, b.thumbCurl, t),
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
    // Poses below were solved for a side grip like holding a cereal box by its
    // edge: palm on the narrow side panel, thumb on the front, fingers wrapped
    // around onto the back. The wrist angles put the hand at that orientation in
    // view (thumb up, fingers pointing into the scene behind the box).
    //
    // Reaching forward and down toward the box, hand open, forearm starting to turn.
    public ArmPose reachPose = new ArmPose
    {
        shoulderPos = new Vector3(0.45f, -0.57f, 0.15f),
        shoulderEuler = new Vector3(8f, -22f, 0f),
        elbowBend = 6f,
        wristEuler = new Vector3(28.931f, 41.539f, 315.401f),
        fingerCurl = 0f,
        forearmRoll = -40f,
        thumbCurl = 0f,
    };
    // Hand closes on the side of the box: thumb onto the front, fingers around the back.
    public ArmPose grabPose = new ArmPose
    {
        shoulderPos = new Vector3(0.45f, -0.57f, 0.15f),
        shoulderEuler = new Vector3(8f, -22f, 0f),
        elbowBend = 6f,
        wristEuler = new Vector3(14.838f, 47.337f, 330.758f),
        fingerCurl = 1f,
        forearmRoll = -60f,
        thumbCurl = 1f,
    };
    // Forearm comes up from below, wrist bent: the box is upright, front facing the player.
    public ArmPose liftPose = new ArmPose
    {
        shoulderPos = new Vector3(0.58f, -0.82f, 0.2f),
        shoulderEuler = new Vector3(12f, -18f, 0f),
        elbowBend = 90f,
        wristEuler = new Vector3(357.102f, 93.02f, 359.223f),
        fingerCurl = 1f,
        forearmRoll = -90f,
        thumbCurl = 1f,
    };
    // Pulled in toward the player: the box is a little closer, front facing
    // the camera, held briefly. Same wrist bend and forearm roll as the lift,
    // so nothing twists.
    public ArmPose pullInPose = new ArmPose
    {
        shoulderPos = new Vector3(0.6f, -0.6f, 0.14f),
        shoulderEuler = new Vector3(10f, -18f, 0f),
        elbowBend = 95f,
        wristEuler = new Vector3(357.011f, 90.007f, 359.738f),
        fingerCurl = 1f,
        forearmRoll = -90f,
        thumbCurl = 1f,
    };
    // Stowed: the same grip lowered straight down out of view, so the exit is
    // a clean drop rather than a turn. (The arm snaps to the hidden rest pose after.)
    public ArmPose stowPose = new ArmPose
    {
        shoulderPos = new Vector3(0.62f, -1.85f, 0.05f),
        shoulderEuler = new Vector3(12f, -18f, 0f),
        elbowBend = 95f,
        wristEuler = new Vector3(357.011f, 90.007f, 359.738f),
        fingerCurl = 1f,
        forearmRoll = -90f,
        thumbCurl = 1f,
    };

    // ─── Lifecycle ───────────────────────────────────────────────────────────
    void Awake()
    {
        if (shoulder == null) BuildArm();
        else ComputeThumbGrip();
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
        ApplyPose(idlePose);          // back to the hidden rest pose for next time
        SetVisible(false);
        OnPickupFinished?.Invoke();
    }

    // ─── Animation ───────────────────────────────────────────────────────────
    // Keyframes over normalized time:
    // rest -> reach -> grab -> lift -> pull in (hold) -> stow straight down.
    public void SampleAt(float t)
    {
        float[] times = { 0f, 0.18f, grabMoment, 0.46f, 0.62f, 0.80f, 1f };
        ArmPose[] poses = { idlePose, reachPose, grabPose, liftPose, pullInPose, pullInPose, stowPose };
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
            if (thumb != null) thumb.localRotation = Quaternion.Slerp(thumbRest, thumbGrip, p.thumbCurl);
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
            thumb = FindDeep(wrist, "FP_Hand_Thumb");
            ComputeThumbGrip();
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

    // The thumb's grip rotation: turn its rest direction (pivot -> middle of the
    // thumb mesh, in wrist space) onto thumbGripDirection. Rest is the import pose.
    void ComputeThumbGrip()
    {
        if (thumb == null || wrist == null) return;
        var mf = thumb.GetComponent<MeshFilter>();
        if (mf == null || mf.sharedMesh == null) return;
        thumbRest = Quaternion.identity;
        Quaternion keep = thumb.localRotation;
        thumb.localRotation = thumbRest;
        Vector3 restDir = wrist.InverseTransformDirection(thumb.TransformDirection(mf.sharedMesh.bounds.center)).normalized;
        Quaternion turn = Quaternion.FromToRotation(restDir, thumbGripDirection.normalized);   // in wrist space
        Quaternion inWrist = Quaternion.Inverse(wrist.rotation) * thumb.rotation;
        thumbGrip = Quaternion.Inverse(thumb.parent.rotation) * (wrist.rotation * turn * inWrist);
        thumb.localRotation = keep;
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
