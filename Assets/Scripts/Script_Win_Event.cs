using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Script_Win_Event : MonoBehaviour
{
    void OnEnable() => Script_CollectibleCount.CollectionComplete += WinScreen;
    private void OnDisable() => Script_CollectibleCount.CollectionComplete -= WinScreen;

    void WinScreen()
    {
        
    }
}
