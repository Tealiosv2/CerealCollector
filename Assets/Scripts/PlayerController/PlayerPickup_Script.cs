using UnityEngine;
using UnityEngine.InputSystem;

// Press E (the "Interact" action) while looking at a collectible to pick it
// up. The first-person arm reaches out to where the box is on screen; when
// the hand closes (FirstPersonArm_Script.OnGrab) the box slides the short
// way into the grip, with a rattle of cereal, and rides along as the arm
// lifts and drops out of view. It is collected when the arm finishes
// (OnPickupFinished).
// Lives on the player camera; aims from the centre of the screen, the same
// way CollectibleHoverOutline_Script picks what to outline.
public class PlayerPickup_Script : MonoBehaviour
{
    public FirstPersonArm_Script arm;
    [Tooltip("How close the player has to be, in world units (the house is ~3x real scale). "
           + "Short enough that the hand can be seen to reach the box: see Aim.")]
    public float reach = 5.5f;

    [Header("Reaching for the box")]
    [Tooltip("Seconds the box takes to slide from where it stood into the closed hand.")]
    public float grabBlend = 0.10f;
    [Tooltip("How far in front of the camera the closed hand can meet the box (camera Z of the held box), nearest and farthest.")]
    public Vector2 handDepthRange = new Vector2(1.0f, 2.0f);
    [Tooltip("How far the arm may slide along its own length, either way, to meet the box.")]
    public float maxArmSlide = 0.6f;

    [Header("Sound")]
    [Tooltip("Cardboard box of cereal being grabbed (Tools/Audio/make_cereal_pickup.py). Starts when the hand closes.")]
    public AudioClip pickupSound;
    [Range(0f, 1f)] public float pickupVolume = 0.8f;
    AudioSource audioSource;

    [Header("Holding (side grip)")]
    [Tooltip("Box scale while held, so it reads as in-hand rather than filling the view.")]
    public float holdScale = 0.36f;
    [Tooltip("Palm surface the box's side panel rests against, in wrist space (palm faces -Y).")]
    public float palmY = -0.040f;
    [Tooltip("Gap between the palm and the box side.")]
    public float palmGap = 0.0f;
    [Tooltip("Where the box centre sits across the hand (wrist X; the thumb side is -X = up the box). "
           + "Negative moves the box up so the hand grips it mid-height.")]
    public float boxCenterAcrossHand = -0.09f;
    [Tooltip("Wrist-space Z of the box's back face: at the knuckles, so the fingers wrap around onto the back and the front sits against the thumb.")]
    public float backEdgeZ = 0.27f;

    // Kept for reference by older tuning scripts; the side grip computes these.
    [HideInInspector] public Vector3 holdOffset = new Vector3(0f, 0.02f, 0.40f);
    [HideInInspector] public Vector3 holdEuler = new Vector3(0f, 180f, 0f);

    Player_InputActions inputActions;
    InputAction interact;
    Camera cam;
    Collectible_Script pending;   // targeted, waiting for the hand to close
    Collectible_Script held;      // in the hand

    // The box sliding from where it stood into the grip.
    Transform blendRoot;
    float blendT;
    Vector3 blendFromPos, blendFromScale, blendToPos, blendToScale;
    Quaternion blendFromRot, blendToRot;

    public bool IsBusy => (arm != null && arm.IsBusy) || held != null || pending != null;

    void Awake()
    {
        cam = GetComponent<Camera>();
        if (arm == null) arm = GetComponentInChildren<FirstPersonArm_Script>();
    }

    void OnEnable()
    {
        inputActions = new Player_InputActions();
        interact = inputActions.Player.Interact;
        interact.performed += OnInteract;
        interact.Enable();
        if (arm != null)
        {
            arm.OnGrab += HandleGrab;
            arm.OnPickupFinished += HandleFinished;
        }
    }

    void OnDisable()
    {
        if (interact != null)
        {
            interact.performed -= OnInteract;
            interact.Disable();
        }
        if (arm != null)
        {
            arm.OnGrab -= HandleGrab;
            arm.OnPickupFinished -= HandleFinished;
        }
    }

    void OnInteract(InputAction.CallbackContext ctx) => TryPickup();

    public bool TryPickup()
    {
        if (arm == null || arm.IsBusy) return false;
        var target = FindTarget();
        if (target == null) return false;
        // Only pick up what is actually highlighted (crosshair on it, in range).
        if (CollectibleHoverOutline_Script.Instance != null && CollectibleHoverOutline_Script.CurrentTarget != target) return false;
        pending = target;
        Aim(target, out Quaternion aim, out Vector3 push);
        arm.PlayPickup(aim, push);
        return true;
    }

    public Collectible_Script FindTarget()
    {
        if (cam == null) return null;
        Ray ray = cam.ViewportPointToRay(new Vector3(0.5f, 0.5f, 0f));
        // Collectibles use trigger colliders, so triggers must be included.
        if (Physics.Raycast(ray, out RaycastHit hit, reach, ~0, QueryTriggerInteraction.Collide))
            return hit.collider.GetComponentInParent<Collectible_Script>();
        return null;
    }

    // Hand closes: cut the box into the hand.
    void HandleGrab()
    {
        if (pending == null) return;
        held = pending;
        pending = null;

        Transform root = RootOf(held);
        foreach (var spin in root.GetComponentsInChildren<CollectibleRotator_Script>()) spin.enabled = false;
        foreach (var col in root.GetComponentsInChildren<Collider>()) col.enabled = false;

        // Work out the grip, then slide the box into it from where it stood
        // (LateUpdate) rather than cutting straight there.
        blendFromPos = root.position;
        blendFromRot = root.rotation;
        Hold(root, held);
        blendToPos = root.localPosition;
        blendToRot = root.localRotation;
        blendToScale = root.localScale;
        blendFromScale = blendToScale / holdScale;
        blendRoot = root;
        blendT = 0f;
        ApplyBlend(0f);

        if (pickupSound != null)
        {
            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.playOnAwake = false;
                audioSource.spatialBlend = 0f;     // it is in the player's own hand
            }
            audioSource.pitch = Random.Range(0.94f, 1.06f);   // no two boxes rattle quite alike
            audioSource.PlayOneShot(pickupSound, pickupVolume);
        }
    }

    // After the arm has posed for this frame.
    void LateUpdate()
    {
        if (blendRoot == null) return;
        blendT += Time.deltaTime / Mathf.Max(grabBlend, 1e-4f);
        ApplyBlend(Mathf.Clamp01(blendT));
        if (blendT >= 1f) blendRoot = null;
    }

    void ApplyBlend(float k)
    {
        k = k * k * (3f - 2f * k);
        blendRoot.position = Vector3.Lerp(blendFromPos, arm.wrist.TransformPoint(blendToPos), k);
        blendRoot.rotation = Quaternion.Slerp(blendFromRot, arm.wrist.rotation * blendToRot, k);
        blendRoot.localScale = Vector3.Lerp(blendFromScale, blendToScale, k);
    }

    static Transform RootOf(Collectible_Script box) => box.transform.parent != null ? box.transform.parent : box.transform;

    // Put the box in the hand: side grip, scaled down, resting in the palm.
    void Hold(Transform root, Collectible_Script box)
    {
        Vector3 worldScale = root.lossyScale;
        root.SetParent(arm.wrist, true);
        root.localScale = Vector3.Scale(worldScale * holdScale, Inv(arm.wrist.lossyScale));
        root.localRotation = SideGripRotation(box);
        PlaceInPalm(root);
    }

    // Aim the reach so the hand closes on the box where the player sees it.
    // The held box is holdScale of its real size, so it looks exactly as big
    // as the real one when it is at holdScale of the distance on the same line
    // of sight: that is where the hand goes, as far as the arm allows
    // (handDepthRange). Then grabbing barely changes the picture. The arm gets
    // there by swinging about the shoulder (aim) and sliding along its own
    // length (push), so it still comes up from the bottom of the view.
    public void Aim(Collectible_Script box, out Quaternion aim, out Vector3 push)
    {
        aim = Quaternion.identity; push = Vector3.zero;
        Transform root = RootOf(box), armRoot = arm.transform;
        var mf = root.GetComponentInChildren<MeshFilter>();
        if (mf == null || mf.sharedMesh == null || arm.wrist == null) return;
        Vector3 World() => mf.transform.TransformPoint(mf.sharedMesh.bounds.center);
        Vector3 boxNow = cam.transform.InverseTransformPoint(World());
        if (boxNow.z <= 0.01f) return;

        // Dry run: hold the box at the unaimed grab pose, note where it sits, put everything back.
        Transform parent = root.parent;
        Vector3 p = root.localPosition, s = root.localScale;
        Quaternion r = root.localRotation;
        arm.ApplyPose(arm.grabPose);
        Hold(root, box);
        Vector3 held = armRoot.InverseTransformPoint(World());
        root.SetParent(parent, false);
        root.localPosition = p; root.localRotation = r; root.localScale = s;
        arm.ApplyPose(arm.idlePose);

        float depth = Mathf.Clamp(boxNow.z * holdScale, handDepthRange.x, handDepthRange.y);
        Vector3 want = armRoot.InverseTransformPoint(cam.transform.TransformPoint(boxNow * (depth / boxNow.z)));
        Vector3 from = held - arm.grabPose.shoulderPos, to = want - arm.grabPose.shoulderPos;
        aim = Quaternion.FromToRotation(from, to);
        push = to.normalized * Mathf.Clamp(to.magnitude - from.magnitude, -maxArmSlide, maxArmSlide);
    }

    // Side grip, as you would hold a cereal box by its edge (wrist space: fingers
    // +Z, palm -Y, thumb -X): palm on the narrow side panel, thumb on the front,
    // fingers running across to the back edge and hooking around it.
    //   box up    -> thumb side (-X)
    //   box front -> back toward the wrist (-Z): faces the player in the front view
    //   box side panel (its width axis) -> against the palm (-Y)
    // The arm bends the wrist so the thumb points up, then turning the forearm
    // shows the front and the back.
    // frontInRoot says which side of this prefab has the front art.
    public static Quaternion SideGripRotation(Collectible_Script box)
    {
        Vector3 front = Vector3.ProjectOnPlane(box.frontInRoot, Vector3.up);
        float frontYaw = front.sqrMagnitude > 1e-6f ? Vector3.SignedAngle(Vector3.forward, front, Vector3.up) : 0f;
        return Quaternion.LookRotation(Vector3.back, Vector3.left) * Quaternion.Euler(0f, -frontYaw, 0f);
    }

    // Slide the (already rotated) box so its side panel rests just under the palm,
    // centred across the hand, with its back face at the middle finger joint.
    public void PlaceInPalm(Transform root)
    {
        var mf = root.GetComponentInChildren<MeshFilter>();
        if (mf == null || mf.sharedMesh == null) return;
        Bounds mb = mf.sharedMesh.bounds;
        Vector3 min = Vector3.positiveInfinity, max = Vector3.negativeInfinity;
        for (int i = 0; i < 8; i++)
        {
            Vector3 corner = mb.center + Vector3.Scale(mb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
            Vector3 w = arm.wrist.InverseTransformPoint(mf.transform.TransformPoint(corner));
            min = Vector3.Min(min, w); max = Vector3.Max(max, w);
        }
        Vector3 shift = new Vector3(
            boxCenterAcrossHand - (min.x + max.x) * 0.5f,   // hand at mid-height on the box
            (palmY - palmGap) - max.y,               // side panel just under the palm
            backEdgeZ - max.z);                      // back face at the middle finger joint
        root.localPosition += shift;
    }

    // Arm is back at rest (off-screen): the box is collected.
    void HandleFinished()
    {
        if (held != null) held.Collect();
        held = null;
    }

    static Vector3 Inv(Vector3 v) => new Vector3(1f / v.x, 1f / v.y, 1f / v.z);
}
