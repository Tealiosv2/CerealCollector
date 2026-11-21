using UnityEngine;

// Keeps Grandma's snore loop in step with her breathing animation: the snore
// clip and the Grandma_SleepSit clip are both one 9 s loop of two breaths
// (see Tools/Audio/make_snore.py), so the audio is nudged back onto the
// animator's loop position whenever the two drift apart.
[RequireComponent(typeof(Animator))]
public class GrandmaSleep_Script : MonoBehaviour
{
    public AudioSource snore;
    [Tooltip("Resync when audio and animation drift apart by more than this (seconds).")]
    public float maxDrift = 0.08f;

    Animator animator;

    void Awake() => animator = GetComponent<Animator>();

    void Start()
    {
        if (snore == null || snore.clip == null) return;
        snore.loop = true;
        if (!snore.isPlaying) snore.Play();
    }

    void Update()
    {
        if (snore == null || snore.clip == null || !snore.isPlaying) return;
        var state = animator.GetCurrentAnimatorStateInfo(0);
        if (state.length <= 0f) return;
        float animTime = (state.normalizedTime % 1f) * snore.clip.length;
        float drift = Mathf.Abs(snore.time - animTime);
        drift = Mathf.Min(drift, snore.clip.length - drift);
        if (drift > maxDrift) snore.time = animTime;
    }
}
