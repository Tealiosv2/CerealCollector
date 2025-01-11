using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class QuantumObject_Script : MonoBehaviour
{
    [SerializeField]
    bool isMoving = true;
    public GameObject QuantumObjecet;
    public GameObject[] positions;
    void OnBecameInvisible()
    {
        if (isMoving)
        {
            RandomMove();
        }

    }

    //decides if object moves
    private void RandomMove()
    {
        int decision = Random.Range(0, 15);
        if (decision > 5)
        {
            int randomPositionIndex = Random.Range(0, positions.Length);
            GameObject randomPosition = positions[randomPositionIndex];
            MoveObject(randomPosition);
        }
    }

    //moves object
    private void MoveObject(GameObject newPosition)
    {
        Debug.Log("Quantum Object Moved");
        transform.position = newPosition.transform.position;
    }
}
