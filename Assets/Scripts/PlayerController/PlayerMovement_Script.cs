using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

public class PlayerMovement_Script : MonoBehaviour
{
    public float speed = 12f;
    public float gravity = -9.81f;
    public float damping = 0.1f; // Damping factor for smoother movement
    public float acceleration = 5f; // Controls how fast the player accelerates
    public float deceleration = 5f; // Controls how fast the player decelerates
    public Transform groundCheck;
    public float groundDistance = 0.4f;
    public float jumpHeight = 3f;
    public LayerMask groundMask;

    private Player_InputActions inputActions;
    private InputAction movement;
    private InputAction jump;
    bool isGrounded;
    Vector3 velocity;
    Vector3 currentVelocity; // Stores current movement velocity
    public CharacterController controller;

    private void Awake()
    {
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
        if (isGrounded && velocity.y < 0)
        {
            velocity.y = -2f;
        }

        // Read input movement
        Vector2 inputVector = movement.ReadValue<Vector2>();
        Vector3 targetVelocity = (transform.right * inputVector.x + transform.forward * inputVector.y) * speed;

        // Smoothly interpolate to the target velocity (applies damping)
        currentVelocity = Vector3.Lerp(currentVelocity, targetVelocity, damping * Time.deltaTime * acceleration);

        // Apply deceleration if no input is present
        if (inputVector == Vector2.zero)
        {
            currentVelocity = Vector3.Lerp(currentVelocity, Vector3.zero, damping * Time.deltaTime * deceleration);
        }

        // Move the player
        controller.Move(currentVelocity * Time.deltaTime);

        // Apply gravity
        velocity.y += gravity * Time.deltaTime;
        controller.Move(velocity * Time.deltaTime);
    }

    private void DoJump(InputAction.CallbackContext obj)
    {
        if (isGrounded)
        {
            velocity.y = Mathf.Sqrt(jumpHeight * -2f * gravity);
        }
    }
}