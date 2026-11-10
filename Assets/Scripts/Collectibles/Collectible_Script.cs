using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// A collectible cereal box. It is no longer collected by walking into it:
// the player looks at it and presses E (see PlayerPickup_Script), and the
// box is collected when the first-person arm's hand closes on it.
public class Collectible_Script : MonoBehaviour
{
    public static event Action OnCollected;
    public static int total;

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
