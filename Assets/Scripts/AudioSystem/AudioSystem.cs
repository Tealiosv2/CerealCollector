using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public enum SoundType
{
    MUSIC
}
[RequireComponent(typeof(AudioSource))]
public class AudioSystem : MonoBehaviour
{

    public AudioSource audioSource;

    void Start()
    {
        if(audioSource == null)
            audioSource = GetComponent<AudioSource>();
        
        PlayMusic();
    }

    public void PlayMusic()
    {
        if(!audioSource.isPlaying)
        {
            audioSource.Play();
        }
    }
}
