using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Unity.VisualScripting;
using UnityEditor.Rendering;
using UnityEngine;

public class DL_DIALOGUE_DATA
{
    public List<DIALOGUE_SEGMENT> segments;
    private const string segmentIdentifierPattern = @"\{[ca]\}|\{w[ca]\s\d*\.?\d*\}";

    public DL_DIALOGUE_DATA(string rawDialogue)
    {
        segments = RipSegments(rawDialogue);
    }
    public List<DIALOGUE_SEGMENT> RipSegments(string rawDialogue)
    {
        List<DIALOGUE_SEGMENT> segments = new List<DIALOGUE_SEGMENT>();
        MatchCollection matches = Regex.Matches(rawDialogue, segmentIdentifierPattern);

        int lastIndex = 0;

        DIALOGUE_SEGMENT segment = new DIALOGUE_SEGMENT();
        segment.dialogue = (matches.Count == 0 ? rawDialogue : rawDialogue.Substring(0, matches[0].Index));
        segment.startSignal = DIALOGUE_SEGMENT.StartSignal.NONE;
        segment.signalDelay = 0;
        segments.Add(segment);

        if (matches.Count == 0)
        {
            return segments;
        }
        else
        {
            lastIndex = matches[0].Index;
        }

        for (int i = 0; i < matches.Count; i++)
        {
            Match match = matches[i];
            segment = new DIALOGUE_SEGMENT();

            //Gets start signal for the segement
            string signalMatch = match.Value;
            signalMatch = signalMatch.Substring(1, match.Length - 2);
            string[] signalSplit = signalMatch.Split(' ');

            segment.startSignal = (DIALOGUE_SEGMENT.StartSignal)Enum.Parse(typeof(DIALOGUE_SEGMENT.StartSignal), signalSplit[0].ToUpper());

            //Get the signal delay
            if (signalSplit.Length > 1)
            {
                float.TryParse(signalSplit[1], out segment.signalDelay);
            }

            //Get the dialogue for the segment
            int nextIndex = i + 1 < matches.Count ? matches[i + 1].Index : rawDialogue.Length;
            segment.dialogue = rawDialogue.Substring(lastIndex + match.Length, nextIndex - (lastIndex + match.Length));
            lastIndex = nextIndex;

            segments.Add(segment);



        }

        return segments;
    }
    public struct DIALOGUE_SEGMENT
    {
        public string dialogue;
        public StartSignal startSignal;
        public float signalDelay;

        public bool isAppendText => (startSignal == StartSignal.A || startSignal == StartSignal.WA);

        public enum StartSignal { NONE, C, A, WA, WC }
    }
}
