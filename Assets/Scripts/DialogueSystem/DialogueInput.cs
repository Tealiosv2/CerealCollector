using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using DIALOGUE;

public class DialogueInput : MonoBehaviour
{
  [SerializeField] private TextAsset fileName;
  void Start()
  {
    StartConversation();
  } 

  void StartConversation()
  {
    List<string> lines = FileManager.ReadTextAsset(fileName);

    DialogueSystem.instance.Say(lines);
  }
}
