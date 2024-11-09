using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;

namespace DIALOGUE
{
    public class DialogueSystem : MonoBehaviour
    {
        public static DialogueSystem instance { get; private set; }
        public DialogueContainer dialogueContainer = new DialogueContainer();
        private TextArchitect architect;
        private ConversationManager conversationManager;
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
            architect = new TextArchitect(dialogueContainer.dialogueText);
            conversationManager = new ConversationManager(architect);
        }
        public Coroutine Say(string speaker, string dialogue)
        {
            List<string> conversation = new List<string>() { $"{speaker} \"{dialogue}\"" };
            return Say(conversation);
        }
        public Coroutine Say(List<string> conversation)
        {
            return conversationManager.StartConversation(conversation);
        }
    }
}