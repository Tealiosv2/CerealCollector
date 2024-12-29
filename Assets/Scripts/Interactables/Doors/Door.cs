using System.Collections;
using UnityEditor.Rendering;
using UnityEngine;

public class Door : MonoBehaviour
{
    public bool isOpen = false;
    [SerializeField]
    private bool isRotatingDoor = true;
    [SerializeField]
    private float openSpeed = 1f;
    [Header("Rotation Configs")]
    [SerializeField]
    private float RoatationAmount = 90f;
    [SerializeField]
    private float ForwardDirection = 0;

    private Vector3 StartRotation;
    private Vector3 Forward;

    private Coroutine AnimationCoroutine;

    private void Awake()
    {
        StartRotation = transform.rotation.eulerAngles;

        Forward = transform.right;
    }

    public void Open(Vector3 UserPosition)
    {
        if (!isOpen)
        {
            if (AnimationCoroutine != null)
            {
                StopCoroutine(AnimationCoroutine);
            }
            if (isRotatingDoor)
            {
                //Determines if player is infront or begind the door's position (Linear alg amirite)
                float dot = Vector3.Dot(Forward, (UserPosition - transform.position).normalized);
                Debug.Log($"Dot: {dot.ToString("N3")}");
                AnimationCoroutine = StartCoroutine(DoRotationOpen(dot));
            }
        }
    }


    private IEnumerator DoRotationOpen(float ForwardAmount)
    {
        Quaternion startRotation = transform.rotation;
        Quaternion endRotation;

        if (ForwardAmount >= ForwardDirection)
        {
            endRotation = Quaternion.Euler(new Vector3(0, StartRotation.y - RoatationAmount, 0));
        }
        else
        {
            endRotation = Quaternion.Euler(new Vector3(0, StartRotation.y + RoatationAmount, 0));
        }

        isOpen = true;

        float time = 0;
        while (time < 1)
        {
            transform.rotation = Quaternion.Slerp(startRotation, endRotation, time);
            yield return null;
            time += Time.deltaTime * openSpeed;
        }
    }

    public void Close()
    {
        if (isOpen)
        {
            if (AnimationCoroutine != null)
            {
                StopCoroutine(AnimationCoroutine);
            }
            if (isRotatingDoor)
            {
                //Determines if player is infront or begind the door's position (Linear alg amirite)
                AnimationCoroutine = StartCoroutine(DoRotationClose());
            }
        }
    }

    private IEnumerator DoRotationClose()
    {

        Quaternion startRotation = transform.rotation;
        Quaternion endRotation = Quaternion.Euler(StartRotation);

        isOpen = false;

        float time = 0;
        while (time < 1)
        {
            transform.rotation = Quaternion.Slerp(startRotation, endRotation, time);
            yield return null;
            time += Time.deltaTime * openSpeed;
        }
    }
}