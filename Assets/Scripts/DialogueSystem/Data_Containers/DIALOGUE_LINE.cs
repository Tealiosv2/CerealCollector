namespace DIALOGUE
{
    public class DIALOGUE_LINE
    {


        public DL_DIALOGUE_DATA dialogueData;
        public DL_COMMAND_DATA commandsData;

        public bool hasDialogue => dialogueData != null;
        public bool hasCommands => commandsData != null;


        public DIALOGUE_LINE(string dialogue, string commands)
        {
            this.dialogueData = (string.IsNullOrWhiteSpace(dialogue) ? null : new DL_DIALOGUE_DATA(dialogue));
            this.commandsData = string.IsNullOrEmpty(commands) ? null : new DL_COMMAND_DATA(commands);
        }
    }

}