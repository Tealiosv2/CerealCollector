using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Script_Win_Event : MonoBehaviour
{
    public Script_LevelLoader levelLoader;
    void OnEnable() => Script_CollectibleCount.CollectionComplete += WinScreen;
    private void OnDisable() => Script_CollectibleCount.CollectionComplete -= WinScreen;

    void WinScreen()
    {
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
        levelLoader.LoadNextLevel();
    }
}
