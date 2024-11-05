using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
public class PlayerMovement_Script : MonoBehaviour
{
    public float speed = 12f;
    public float gravity = -9.81f;
    public Transform groundCheck;
    public float groundDistance = 0.4f;
    public float jumpHeight = 3f;
    public LayerMask groundMask;

    private Player_InputActions inputActions;
    private InputAction movement;
    private InputAction jump;
    bool isGrounded;
    Vector3 velocity;
    public CharacterController controller;

    private void Awake(){
        inputActions = new Player_InputActions();
    }
    private void OnEnable()
    {
        movement = inputActions.Player.Movement;
        jump = inputActions.Player.Jump;
        movement.Enable();
        jump.Enable();

        jump.performed += DoJump;
    }
    private void OnDisable()
    {
        movement.Disable();
        jump.Disable();
    }
    void FixedUpdate()
    {
        isGrounded = Physics.CheckSphere(groundCheck.position, groundDistance, groundMask);
        if (isGrounded && velocity.y < 0){
            velocity.y = -2f;
        }

        Vector2 v2 = movement.ReadValue<Vector2>();

        Vector3 move = transform.right * v2.x + transform.forward * v2.y;

        controller.Move(move * speed * Time.deltaTime);

        velocity.y += gravity * Time.deltaTime;

        controller.Move(velocity * Time.deltaTime);
    }

    private void DoJump(InputAction.CallbackContext obj)
    {
        if(isGrounded){
            velocity.y = Mathf.Sqrt(jumpHeight * -2f * gravity);
        }
    }

}
