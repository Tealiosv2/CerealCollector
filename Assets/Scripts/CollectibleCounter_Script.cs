using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

public class Script_CollectibleCount : MonoBehaviour
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

    void OnEnable() => Script_MeatLoop.OnCollected += OnCollectibleCollected;
    private void OnDisable() => Script_MeatLoop.OnCollected -= OnCollectibleCollected;

    void OnCollectibleCollected()
    {
        count++;
        UpdateCount();
        if(Script_MeatLoop.total == count)
        {
            CollectionComplete?.Invoke();
        }
    }



    void UpdateCount()
    {
        text.text = $"{count} / {Script_MeatLoop.total}";
    }
}
