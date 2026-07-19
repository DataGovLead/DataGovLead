# Install the profile refresh

This bundle is designed for the public profile repository:

`DataGovLead/DataGovLead`

## Recommended installation

1. Create a branch in the profile repository.
2. Copy the bundle contents into the repository root.
3. Review `README.md` and `profile.json`.
4. Open a pull request and inspect the rendered README.
5. Merge the pull request.
6. Run **Refresh profile** once from the Actions tab.

## Adding another featured project

Add another object to `profile.json`:

```json
{
  "repository": "repository-name",
  "display_name": "Display name",
  "summary": "One concise sentence explaining the value.",
  "stack": ["Python", "SQL"],
  "status": "Active",
  "allow_fork": false
}
```

Then run:

```bash
python scripts/update_profile.py
python scripts/update_profile.py --check
```

The scheduled workflow runs each Monday at 07:17 UTC. It validates that
featured repositories are public, unarchived, and not forks unless explicitly
allowed.

## Repository settings

Under **Settings → Actions → General**:

- Permit GitHub Actions for the repository.
- Keep the default `GITHUB_TOKEN` workflow permissions restrictive; the refresh
  workflow declares only `contents: write`.
- Consider enabling the repository policy that requires actions to be pinned to
  full-length commit SHAs.

The workflows in this bundle already pin GitHub-maintained actions to immutable
full commit SHAs.
