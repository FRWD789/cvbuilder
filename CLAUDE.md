# cvBuilder

Job-application pipeline. The workflows live in `.claude/skills/` (`apply` orchestrates `job-match`, `cv-builder` and `cv-design`); follow their SKILL.md files.

- The user's data is in `profile/master-profile.json`. If it doesn't exist yet, offer to create it from `profile/master-profile.example.json`, from the user's CV file, or from their answers.
- Every application goes in `output/<YYYY-MM-DD>_<company-slug>/`; the tracker is `suivi-candidatures.xlsx` at the root.
- Never invent facts. Never edit the master profile without the user's confirmation. Never submit anything on the user's behalf.
