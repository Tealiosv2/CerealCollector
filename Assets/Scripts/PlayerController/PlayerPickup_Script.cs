using UnityEngine;
using UnityEngine.InputSystem;

// Press E (the "Interact" action) while looking at a collectible to pick it
// up. The first-person arm plays its pick-up animation; when the hand closes
// (FirstPersonArm_Script.OnGrab) the cereal box cuts into the hand and rides
// along as the arm lifts and drops out of view, and it is collected when the
// arm finishes (OnPickupFinished).
// Lives on the player camera; aims from the centre of the screen, the same
// way CollectibleHoverOutline_Script picks what to outline.
public class PlayerPickup_Script : MonoBehaviour
{
    public FirstPersonArm_Script arm;
    public float reach = 8f;                 // world units (the house is ~3x real scale)

    [Header("Holding")]
    [Tooltip("Where the box's centre sits, in the wrist's local space (in front of the palm).")]
    public Vector3 holdOffset = new Vector3(0f, 0.02f, 0.40f);
    [Tooltip("Box scale while held, so it reads as in-hand rather than filling the view.")]
    public float holdScale = 0.45f;
    [Tooltip("Box rotation in the hand (wrist space). 180 on Y turns the box front toward the player.")]
    public Vector3 holdEuler = new Vector3(0f, 180f, 0f);

    Player_InputActions inputActions;
    InputAction interact;
    Camera cam;
    Collectible_Script pending;   // targeted, waiting for the hand to close
    Collectible_Script held;      // in the hand

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
        pending = target;
        arm.PlayPickup();
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

        Transform root = held.transform.parent != null ? held.transform.parent : held.transform;
        foreach (var spin in root.GetComponentsInChildren<CollectibleRotator_Script>()) spin.enabled = false;
        foreach (var col in root.GetComponentsInChildren<Collider>()) col.enabled = false;

        Vector3 worldScale = root.lossyScale;
        root.SetParent(arm.wrist, true);
        root.localRotation = Quaternion.Euler(holdEuler);
        root.localScale = Vector3.Scale(worldScale * holdScale, Inv(arm.wrist.lossyScale));

        // Put the centre of the box (not its pivot) at the hold point.
        var r = root.GetComponentInChildren<Renderer>();
        Vector3 holdPoint = arm.wrist.TransformPoint(holdOffset);
        root.position += holdPoint - (r != null ? r.bounds.center : root.position);
    }

    // Arm is back at rest (off-screen): the box is collected.
    void HandleFinished()
    {
        if (held != null) held.Collect();
        held = null;
    }

    static Vector3 Inv(Vector3 v) => new Vector3(1f / v.x, 1f / v.y, 1f / v.z);
}
