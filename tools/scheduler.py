from __future__ import annotations

import subprocess

def register_scheduler_tools(mcp) -> None:

    @mcp.tool()
    def squeue_me() -> dict:
        """
        Return current SLURM jobs for user.
        Shows job ID, name, state, runtime and partition.
        """
        result = subprocess.run(
            ["squeue", "--me", "--format=%i|%j|%T|%M|%P|%R", "--noheader"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"squeue failed: {result.stderr.strip()}")

        jobs = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 6:
                continue
            jobs.append({
                "job_id": parts[0],
                "name": parts[1],
                "state": parts[2],
                "runtime": parts[3],
                "partition": parts[4],
                "reason": parts[5]
            })
    
        return {"job_count": len(jobs), "jobs": jobs}
