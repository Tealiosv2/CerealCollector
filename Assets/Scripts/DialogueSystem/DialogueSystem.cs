using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;

namespace DIALOGUE
{
    public class DialogueSystem : MonoBehaviour
    {
        public static DialogueSystem instance { get; private set; }
        public DialogueContainer dialogueContainer = new DialogueContainer();
        private void Awake()
        {
            if (instance == null)
            {
                instance = this;
                Initialize();
            }
            else
            {
                DestroyImmediate(gameObject);
            }
        }

        bool _initialized = false;
        private void Initialize()
        {
            if (_initialized)
            {
                return;
            }
            //architect = new TextArchitect()
        }
    }
}