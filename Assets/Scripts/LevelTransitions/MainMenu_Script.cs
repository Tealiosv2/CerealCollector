using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

public class MainMenu_Script : MonoBehaviour
    
{
    public LevelLoader_Script levelLoader;
    public void PlayGame()
    {
        levelLoader.LoadNextLevel();
    }

    public void QuitGame()
    {
        Application.Quit();
    }
}
