# Security disclaimer

This repository is an **intentionally vulnerable** training lab, built for a
conference demo. The vulnerabilities in it are the whole point — do not report
them as bugs, and do not "fix" them if you want the lab to work.

## What is dangerous here

- **Working remote code execution.** The `debug_connection` tool runs attacker
  input through a shell. Anyone who can reach the chat can run commands in the
  container as root.
- **An overprivileged cloud role.** The AWS deploy attaches an instance role
  with `AmazonEC2FullAccess`, `AmazonS3FullAccess` and `IAMFullAccess`. Through
  IMDS, the RCE above becomes credentials that are effectively admin on the
  whole AWS account.
- **A guardrail-free internal agent** that dumps synthetic PII to anyone holding
  a static bearer token, which the RCE leaks.

## Rules for running it

- Use a **throwaway / dedicated AWS account**. Never your main account.
- Keep the security group **locked to your own IP**. Do not expose the lab to
  the internet or to an untrusted audience network.
- Run `./deploy/teardown.sh` as soon as you are done. The overprivileged role
  and the live RCE must not outlive the demo.
- All data in the lab is synthetic. Do not add real credentials or real PII.

## Reporting

There is no security contact for the lab itself — the flaws are deliberate. If
you find a real secret, real PII, or a real credential committed to this repo
by mistake (as opposed to the intentional decoys), open an issue or contact
[Riyaz Walikar](https://ibreak.software) and it will be scrubbed.
