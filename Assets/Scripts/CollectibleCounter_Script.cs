using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

public class CollectibleCounter_Script : MonoBehaviour
{
    public static event Action CollectionComplete;
    TMPro.TMP_Text text;
    int count;

    private void Awake()
    {
        text = GetComponent<TMPro.TMP_Text>();
    }

    private void Start()
    {
        UpdateCount();
    }

    void OnEnable() => Collectible_Script.OnCollected += OnCollectibleCollected;
    private void OnDisable() => Collectible_Script.OnCollected -= OnCollectibleCollected;

    void OnCollectibleCollected()
    {
        count++;
        UpdateCount();
        if(Collectible_Script.total == count)
        {
            CollectionComplete?.Invoke();
        }
    }



    void UpdateCount()
    {
        text.text = $"{count} / {Collectible_Script.total}";
    }
}
