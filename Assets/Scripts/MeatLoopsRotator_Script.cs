using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Rotator : MonoBehaviour
{
    private void Update()
    {
        //transform.localRotation = Quaternion.Euler(90f, Time.time* 100f, 0);
        transform.Rotate(0f, 90f * Time.deltaTime, 0f);
    }
}
