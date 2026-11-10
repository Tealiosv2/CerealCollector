using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// A collectible cereal box. It is no longer collected by walking into it:
// the player looks at it (outlined, in range) and presses E (see
// PlayerPickup_Script). The arm picks it up, inspects it, and it is collected
// once the arm has lowered it out of view.
public class Collectible_Script : MonoBehaviour
{
    public static event Action OnCollected;
    public static int total;

    [Tooltip("Which side of the box has the front art, in the prefab root's local space. "
           + "Used to turn the box toward the player when it is picked up and inspected.")]
    public Vector3 frontInRoot = Vector3.forward;

    bool collected;

    private void Awake()
    {
        total++;
    }

    public void Collect()
    {
        if (collected) return;
        collected = true;
        OnCollected?.Invoke();
        Destroy(transform.parent.gameObject);
    }
}
