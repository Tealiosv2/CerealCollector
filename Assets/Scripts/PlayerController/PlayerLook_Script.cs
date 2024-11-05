using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerLook_Script : MonoBehaviour
{
    public Transform playerBody;
    float xRotation = 0f;
    public float mouseSensitivity = 100f;
    void Start()
    {
       Cursor.lockState = CursorLockMode.Locked; 
    }

    // Update is called once per frame
    void Update()
    {
      //change input system later 
       float mouseX = Input.GetAxis("Mouse X") * mouseSensitivity * Time.deltaTime;
       float mouseY = Input.GetAxis("Mouse Y") * mouseSensitivity * Time.deltaTime;

       xRotation -= mouseY;
       xRotation = Mathf.Clamp(xRotation, -90f, 90f);

       transform.localRotation = Quaternion.Euler(xRotation, 0f, 0f);
       playerBody.Rotate(Vector3.up * mouseX);

    }
}
