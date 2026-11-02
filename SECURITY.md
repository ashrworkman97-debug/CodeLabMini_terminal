# Security Policy

CLM-1 is an experimental hobby project. Please use the latest version on the `main` branch when checking whether an issue is still present.

## Reporting a vulnerability

Please **do not** publish API keys, private macro files, exploit details, or other sensitive information in a public issue.

If GitHub's private vulnerability reporting is enabled for this repository, use the **Security** tab to report the issue privately. If it is not enabled, contact the maintainer through the GitHub profile and ask for a private reporting channel before sending technical details.

Include the affected CLM-1 version, the affected file or feature, the conditions required to reproduce the issue, and its potential impact. Do not include real API keys or other credentials.

## Security notes

- Keep `OPENAI_API_KEY` and `~/.config/clm-1/` private.
- Local configuration and generated custom-command files do not belong in Git.
- AI-created commands are validated declarative actions, not executable Python or shell code. This reduces risk but is not a guarantee that every hardware effect is safe in every setup.
- Review a generated macro before saving or running it, and do not leave hardware effects operating unattended.
- CLM-1 sends AI command-generation requests to the OpenAI API only when the optional AI feature is used.
