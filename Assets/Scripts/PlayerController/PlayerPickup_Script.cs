using UnityEngine;
using UnityEngine.InputSystem;

// Press E (the "Interact" action) while looking at a collectible to pick it
// up: the first-person arm plays its pick-up animation and the item is
// collected the moment the hand closes (FirstPersonArm_Script.OnGrab).
// Lives on the player camera; aims from the centre of the screen, the same
// way CollectibleHoverOutline_Script picks what to outline.
public class PlayerPickup_Script : MonoBehaviour
{
    public FirstPersonArm_Script arm;
    public float reach = 8f;          // world units (the house is ~3x real scale)

    Player_InputActions inputActions;
    InputAction interact;
    Camera cam;
    Collectible_Script pending;

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
        if (arm != null) arm.OnGrab += HandleGrab;
    }

    void OnDisable()
    {
        if (interact != null)
        {
            interact.performed -= OnInteract;
            interact.Disable();
        }
        if (arm != null) arm.OnGrab -= HandleGrab;
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

    void HandleGrab()
    {
        if (pending != null) pending.Collect();
        pending = null;
    }
}
