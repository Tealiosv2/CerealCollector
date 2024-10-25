using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

public class LevelLoader_Script : MonoBehaviour
{
    public Animator transition;
    public float transitionTime = 3f;
    // Update is called once per frame

    public void LoadNextLevel()
    {
        StartCoroutine(LoadLevel(SceneManager.GetActiveScene().buildIndex + 1));
    }

    IEnumerator LoadLevel(int levelIndex)
    {
        transition.SetTrigger("Start");
        
        SceneManager.LoadScene("Scene_LoadingScreen", LoadSceneMode.Additive);
        yield return new WaitForSeconds(transitionTime);
        AsyncOperation asyncLoad = SceneManager.LoadSceneAsync(levelIndex);
        asyncLoad.allowSceneActivation = true;
        while (!asyncLoad.isDone) {
            yield return null;
        }
       
    }
}
