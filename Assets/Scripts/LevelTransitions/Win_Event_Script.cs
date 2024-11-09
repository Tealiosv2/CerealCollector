using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Win_Event_Script : MonoBehaviour
{
    public LevelLoader_Script levelLoader;
    void OnEnable() => CollectibleCounter_Script.CollectionComplete += WinScreen;
    private void OnDisable() => CollectibleCounter_Script.CollectionComplete -= WinScreen;

    void WinScreen()
    {
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
        levelLoader.LoadNextLevel();
    }
}
