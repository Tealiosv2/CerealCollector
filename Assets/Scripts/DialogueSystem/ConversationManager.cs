using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace DIALOGUE
{
    public class ConversationManager
    {
        private DialogueSystem dialogueSystem => DialogueSystem.instance;
        private TextArchitect architect = null;

        private Coroutine process = null;
        public bool isRunning => process != null;


        public ConversationManager(TextArchitect architect)
        {
            this.architect = architect;
        }

        public Coroutine StartConversation(List<string> conversation)
        {
            StopConversation();

            process = dialogueSystem.StartCoroutine(RunningConversation(conversation));
            return process;
        }

        public void StopConversation()
        {
            if (!isRunning)
            {
                return;
            }
            dialogueSystem.StopCoroutine(process);
            process = null;
        }

        IEnumerator RunningConversation(List<string> conversation)
        {
            for (int i = 0; i < conversation.Count; i++)
            {
                if (string.IsNullOrWhiteSpace(conversation[i]))
                {
                    continue;
                }
                DIALOGUE_LINE line = DialogueParser.Parse(conversation[i]);

                if (line.hasDialogue)
                {
                    yield return Line_RunDialogue(line);
                }


                if (line.hasCommands)
                {
                    //yield return Line_RunCommands(line);
                    yield return null;
                }


            }

            process = null;

        }
        IEnumerator Line_RunDialogue(DIALOGUE_LINE line)
        {

            yield return BuildLineSegments(line.dialogueData);

        }
        // IEnumerator Line_RunCommands(DIALOGUE_LINE line)
        // {
        //     List<DL_COMMAND_DATA.Command> commands = line.commandsData.commands;

        //     foreach (DL_COMMAND_DATA.Command command in commands)
        //     {
        //         if (command.waitForCompletion)
        //         {
        //             yield return CommandManager.instance.Execute(command.name, command.arguments);
        //         }
        //         else
        //         {
        //             CommandManager.instance.Execute(command.name, command.arguments);
        //         }
        //     }
        //     yield return null;
        // }
        IEnumerator BuildLineSegments(DL_DIALOGUE_DATA line)
        {
            for (int i = 0; i < line.segments.Count; i++)
            {
                DL_DIALOGUE_DATA.DIALOGUE_SEGMENT segment = line.segments[i];


                yield return BuildDialogue(segment.dialogue, segment.isAppendText);
            }
        }
        IEnumerator BuildDialogue(string dialogue, bool append = false)
        {
            //builds dialogue
            if (!append)
                architect.Build(dialogue);
            else
                architect.Append(dialogue);

            yield return null;
        }
    }
}