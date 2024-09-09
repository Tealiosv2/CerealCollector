using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Script_CollectibleCount : MonoBehaviour
{
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

    void OnEnable() => Script_Collectible.OnCollected += OnCollectibleCollected;
    private void OnDisable() => Script_Collectible.OnCollected -= OnCollectibleCollected;

    void OnCollectibleCollected()
    {
        count++;
        UpdateCount();
    }

    void UpdateCount()
    {
        text.text = $"{count} / {Script_Collectible.total}";
    }
}
