#!/usr/bin/env node
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

async function runSkillsRef() {
  try {
    const { stdout, stderr } = await execAsync(
      'uvx --from git+https://github.com/agentskills/agentskills.git#subdirectory=skills-ref skills-ref'
    );
    console.log(stdout);
    if (stderr) {
      console.error(stderr);
    }
  } catch (error) {
    console.error('Error running skills-ref:', error.message);
    process.exit(1);
  }
}

runSkillsRef();
