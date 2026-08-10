const { spawnSync } = require('child_process');
const os = require('os');

function tryCandidate(cmd, args) {
  try {
    const result = spawnSync(cmd, args, { encoding: 'utf-8', timeout: 10000 });
    if (result.status === 0) {
      return result.stdout.trim();
    }
  } catch {
    /* ignore spawn error */
  }
  return null;
}

function parseVersion(versionStr) {
  const parts = versionStr.split('.').map(Number);
  return { major: parts[0] || 0, minor: parts[1] || 0, patch: parts[2] || 0 };
}

function meetsRequirement(version) {
  return version.major > 3 || (version.major === 3 && version.minor >= 12);
}

function getPythonCandidates() {
  const platform = os.platform();
  if (platform === 'win32') {
    return [
      { cmd: 'py', args: ['-3.12', '-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
      { cmd: 'py', args: ['-3', '-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
      { cmd: 'python', args: ['-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
    ];
  }
  return [
    { cmd: 'python3.12', args: ['-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
    { cmd: 'python3', args: ['-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
    { cmd: 'python', args: ['-c', 'import sys; print(".".join(str(v) for v in sys.version_info[:3]))'] },
  ];
}

function findPython() {
  const candidates = getPythonCandidates();
  for (const { cmd, args } of candidates) {
    const versionStr = tryCandidate(cmd, args);
    if (versionStr) {
      const version = parseVersion(versionStr);
      if (meetsRequirement(version)) {
        const fullPath = tryCandidate(cmd, ['-c', 'import sys; print(sys.executable)']);
        if (fullPath) {
          return { path: fullPath, version };
        }
      }
    }
  }
  return null;
}

module.exports = { findPython };
