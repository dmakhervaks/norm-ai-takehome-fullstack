LLM_STRUCTURING_PROMPT = (
    "You are a legal document parser. Please analyze the following legal text and structure it into sections.\n\n"
    "The sections may be nested with subsections, like a tree. The child of the tree (i.e. the most nested subsection) should be treated as its own section, prepended with any\n"
    "other text from its parent sections. \n\n"
    "For example, if the text is:\n\n"
    "```\n"
    "3.\n"
    "Widows\n"
    "3.1.\n"
    "The Widow's Law reaffirms the right of the eldest son (or eldest daughter, if there\n"
    "are no sons) to inherit.\n"
    "3.1.1.\n"
    "However, the law requires the heirs to maintain their father's surviving\n"
    "widow, no matter whether she had been a second, third, or even later\n"
    "wife, under the same conditions as she had been before her husband’s\n"
    "death.\n"
    "```\n\n"
    "Then the section title should be \"Widows\".\n"
    "The section number should be \"3.1.1\" (the most nested subsection)\n"
    "The section content should be \"The Widow's Law reaffirms the right of the eldest son (or eldest daughter, if there\n"
    "are no sons) to inherit. However, the law requires the heirs to maintain their father's surviving widow, no matter whether she had been a second, third, or even later wife, under the same conditions as she had been before her husband’s death.\"\n\n"
    "Which is the content of all of the text from the parent sections, plus the content of the most nested subsection.\n\n"
    "Raw text to parse:\n{content}...\n"
)


LLM_STRUCTURING_PROMPT_GENERAL = (
    "You are a legal document parser. Please analyze the following legal text and structure it into sections.\n\n"
    "The sections may be nested with subsections, like a tree. Only the most nested subsection should be treated as its own section.\n"
    "The titles and subtitles should be part of the section title and the most nested subsection should be the section content.\n\n"
    "The section may also be a list of items with XML, HTTP, or other formats for tags, heading size, etc.\n"
    "Please use your best judgement to determine the section title, section number, and section content.\n"
    "The sections should be relatively compact and contain similar information. Your job is not do re-write or re-organize the text.\n"
    "But rather create sections from the existing text, keeping only relevant information and removing things like formatting, footnotes, etc.\n"
    "Raw text to parse:\n{content}...\n"
)


