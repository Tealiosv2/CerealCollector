using System.Collections;
using System.Collections.Generic;
using UnityEditor.Search;
using UnityEngine;

public class QuantumObject_Script : MonoBehaviour
{
    public GameObject QuantumObjecet;
    public GameObject[] positions;
    void OnBecameInvisible()
    {
        RandomMove();
    }

    //returns a random transform decide if object moves
    private void RandomMove()
    {
        int decision = Random.Range(0, 15);
        if (decision > 5)
        {
            Debug.Log("Object Moves");
            int randomPositionIndex = Random.Range(0, positions.Length);
            GameObject randomPosition = positions[randomPositionIndex];
            MoveObject(randomPosition);
        }
        Debug.Log("Object doesn't move");
    }

    //moves object
    private void MoveObject(GameObject newPosition)
    {
        transform.position = newPosition.transform.position;
    }
}
