using UnityEngine;
using System.Text.RegularExpressions;

/**
 * DialogueParser is responsible for parsing a raw dialogue line into its dialogue content and associated commands.
 * It identifies the dialogue content enclosed in double quotes and separates it from any commands that may be present.
 * The parser also handles escaped characters within the dialogue content.
 */
namespace DIALOGUE
{
    public class DialogueParser
    {
        const string commandRegexPattern = @"[\w\[\]]*[^\s]\(";

        public static DIALOGUE_LINE Parse(string rawLine)
        {
            (string dialogue, string commands) = RipContent(rawLine);
            return new DIALOGUE_LINE(dialogue, commands);
        }

        static (string, string) RipContent(string rawLine)
        {

            string dialogue = "";
            string commands = "";

            int dialogueStart = -1;
            int dialogueEnd = -1;
            bool isEscaped = false;

            for (int i = 0; i < rawLine.Length; i++)
            {
                char current = rawLine[i];
                if (current == '\\')
                {
                    isEscaped = !isEscaped;
                }
                else if (current == '"' && !isEscaped)
                {
                    if (dialogueStart == -1)
                    {
                        dialogueStart = i;
                    }
                    else if (dialogueEnd == -1)
                    {
                        dialogueEnd = i;
                    }
                    else
                    {
                        isEscaped = false;
                    }
                }
            }
            Regex commandRegex = new Regex(commandRegexPattern);
            MatchCollection matches = commandRegex.Matches(rawLine);
            int commandStart = -1;

            foreach (Match match in matches)
            {
                if (match.Index < dialogueStart || match.Index > dialogueEnd)
                {
                    commandStart = match.Index;
                    break;
                }
            }
            if (commandStart != -1 && (dialogueStart == -1 && dialogueEnd == -1))
            {
                return ("", rawLine.Trim());
            }
            if (dialogueStart != -1 && dialogueEnd != -1 && (commandStart == -1 || commandStart > dialogueEnd))
            {
                //stuff here missing
                dialogue = rawLine.Substring(dialogueStart + 1, dialogueEnd - dialogueStart - 1).Replace("\\\"","\"");

                if (commandStart != -1)
                {
                    commands = rawLine.Substring(commandStart).Trim();
                }
            }
            else if (commandStart != -1 && dialogueStart > commandStart)
            {
                commands = rawLine;
            }
            else
            {
                dialogue = rawLine;
            }

            return (dialogue, commands);

        }
    }
}