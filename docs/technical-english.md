# ASD-STE100 technical-English policy

All Athena English technical prose must follow
[ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/). This requirement applies to
skills, agent directions, public documents, user messages that a skill produces, and text in a user
interface.

The engineering principles in `docs/principles/**` do not have to follow this policy. The literal
text that this policy identifies also does not have to follow it.

## Authority

Use the current official issue of ASD-STE100 as the authority. Request a copy from the
[official download page](https://www.asd-ste100.org/STE_downloads.html).

This repository policy does not copy or replace the standard. It does not replace approved
training. Repository checks can find Markdown errors, broken package contracts, and some style
risks. The checks do not certify conformance to ASD-STE100.

## Required method

Use these steps when you write or change technical prose:

1. Read the applicable technical source before you write.
2. Use approved words with their approved meanings and parts of speech.
3. Use a technical noun or a technical verb when the approved dictionary has no necessary term.
4. Use one term for one meaning. Do not use a different synonym for the same item or action.
5. Use American English spelling unless an exact external name uses a different spelling.
6. Use active voice when you know the actor. Use the imperative form for a direct instruction.
7. Put a condition before the related action when the reader must know the condition first.
8. Give one primary instruction in each numbered step.
9. Keep sentences short. Split a sentence when it contains more than one independent idea.
10. Use a vertical list when it makes complex information easier to identify.
11. Avoid an `-ing` form when an approved, unambiguous form gives the same meaning.
12. Define each abbreviation at its first use unless the intended readers always know it.
13. Keep the technical meaning. Do not remove a necessary safety, evidence, permission, or failure
    condition to make a sentence shorter.
14. Review the result against the current official standard.

## Literal text

Do not change literal text only to make it conform to this policy. Literal text includes:

- source code and generated code;
- commands, options, identifiers, paths, URLs, and API field names;
- machine-readable markers, schemas, and data values;
- legal text, licenses, and required notices;
- attributed quotations; and
- historical records that must preserve their original text.

Write the prose around literal text in accordance with ASD-STE100. Use code formatting or a
quotation format to make the literal boundary clear.

## Conflict and verification

Technical accuracy, safety controls, security controls, evidence rules, and higher-authority
instructions take precedence. If simplified wording changes the required meaning, keep the meaning
and rewrite the sentence again. Ask for a technical review when you cannot remove the ambiguity.

If you cannot use the current official standard, apply this policy and report the verification gap.
Do not state that the text conforms to ASD-STE100. Do not state that a person or tool certified or
verified the text.
