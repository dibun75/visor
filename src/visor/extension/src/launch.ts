/**
 * Pure helpers that decide how the HUD extension finds `uv` and launches
 * `visor-mcp`. They do not import `vscode`, so they can be unit tested
 * with `node --test` without a VS Code window.
 */
import * as path from 'path';

export interface HostInfo {
    platform: NodeJS.Platform;
    env: NodeJS.ProcessEnv;
}

function pathApi(platform: NodeJS.Platform): path.PlatformPath {
    return platform === 'win32' ? path.win32 : path.posix;
}

function homeDir({ platform, env }: HostInfo): string {
    if (platform === 'win32') {
        return env.USERPROFILE || env.HOME || '';
    }
    return env.HOME || '';
}

/** PATH separator for the target platform. */
export function pathDelimiter(platform: NodeJS.Platform): string {
    return platform === 'win32' ? ';' : ':';
}

/**
 * Directories where `uv` is commonly installed, most specific first.
 * Used both to probe for the binary and to extend PATH for the server.
 */
export function uvSearchDirs(host: HostInfo): string[] {
    const p = pathApi(host.platform);
    const home = homeDir(host);
    const env = host.env;
    const dirs: string[] = [];

    // Explicit installer overrides apply on every platform.
    if (env.UV_INSTALL_DIR) dirs.push(env.UV_INSTALL_DIR);
    if (env.XDG_BIN_HOME) dirs.push(env.XDG_BIN_HOME);

    if (host.platform === 'win32') {
        if (home) {
            // Standalone installer (current and older layouts) and Scoop.
            dirs.push(p.join(home, '.local', 'bin'));
            dirs.push(p.join(home, '.cargo', 'bin'));
            dirs.push(p.join(home, 'scoop', 'shims'));
        }
        if (env.LOCALAPPDATA) {
            // WinGet links and per-user installs.
            dirs.push(p.join(env.LOCALAPPDATA, 'Microsoft', 'WinGet', 'Links'));
            dirs.push(p.join(env.LOCALAPPDATA, 'Programs', 'uv'));
        }
        if (env.ProgramData) {
            dirs.push(p.join(env.ProgramData, 'chocolatey', 'bin'));
        }
    } else {
        if (home) {
            dirs.push(p.join(home, '.local', 'bin'));
            dirs.push(p.join(home, '.cargo', 'bin'));
        }
        dirs.push('/opt/homebrew/bin');
        dirs.push('/usr/local/bin');
        dirs.push('/usr/bin');
    }

    return Array.from(new Set(dirs.filter(Boolean)));
}

/** Full candidate paths to the `uv` binary for the target platform. */
export function uvCandidatePaths(host: HostInfo): string[] {
    const p = pathApi(host.platform);
    const exe = host.platform === 'win32' ? 'uv.exe' : 'uv';
    return uvSearchDirs(host).map((dir) => p.join(dir, exe));
}

/** PATH with the common uv locations prepended. */
export function augmentedPath(host: HostInfo): string {
    const current = host.env.PATH || host.env.Path ||
        (host.platform === 'win32' ? '' : '/usr/bin:/bin');
    return [...uvSearchDirs(host), current]
        .filter(Boolean)
        .join(pathDelimiter(host.platform));
}

export interface ResolveUvDeps {
    /** Returns whether a file exists. */
    exists: (file: string) => boolean;
    /**
     * Runs a lookup command (`where` on Windows, `which` elsewhere) and
     * returns stdout, or throws when the command fails.
     */
    lookup: (command: string, args: string[], env: NodeJS.ProcessEnv) => string;
}

/**
 * Resolve the absolute path to `uv`. Tries the platform's PATH lookup with
 * an augmented PATH, then the known install locations, then falls back to
 * the bare command name.
 */
export function resolveUvPath(host: HostInfo, deps: ResolveUvDeps): string {
    const win = host.platform === 'win32';
    const env = { ...host.env, PATH: augmentedPath(host) };
    try {
        const out = deps.lookup(win ? 'where' : 'which', ['uv'], env);
        // `where` can print several matches, one per line.
        const found = out.split(/\r?\n/).map((s) => s.trim()).find(Boolean);
        if (found && deps.exists(found)) return found;
    } catch {
        // fall through to the candidate list
    }

    for (const candidate of uvCandidatePaths(host)) {
        if (deps.exists(candidate)) return candidate;
    }

    return win ? 'uv.exe' : 'uv';
}

export interface LaunchInputs {
    uvPath: string;
    workspaceFolder: string;
    /** Value of the `visor.serverPath` setting, already trimmed. */
    customServerPath?: string;
    /** Whether `<workspace>/src/visor/server.py` exists. */
    localServerExists: boolean;
    /** Path to `<workspace>/src/visor/server.py`. */
    localServerPath: string;
}

export interface LaunchPlan {
    command: string;
    args: string[];
    /** True when `uv` is the launcher and must be pre-flighted. */
    usesUv: boolean;
    reason: 'configured-python' | 'configured-executable' | 'local-checkout' | 'uv-tool';
}

/**
 * Decide how to launch `visor-mcp`:
 *   - a configured `server.py` path runs with `uv run`;
 *   - a configured executable runs directly and does not need `uv`;
 *   - a workspace with `src/visor/server.py` runs that file with `uv run`;
 *   - otherwise `uv tool run visor-mcp`.
 */
export function chooseServerLaunch(input: LaunchInputs): LaunchPlan {
    const { uvPath, workspaceFolder, customServerPath } = input;
    if (customServerPath) {
        if (customServerPath.toLowerCase().endsWith('.py')) {
            return {
                command: uvPath,
                args: ['--directory', workspaceFolder, 'run', '-q', customServerPath],
                usesUv: true,
                reason: 'configured-python',
            };
        }
        return {
            command: customServerPath,
            args: [],
            usesUv: false,
            reason: 'configured-executable',
        };
    }
    if (input.localServerExists) {
        return {
            command: uvPath,
            args: ['--directory', workspaceFolder, 'run', '-q', input.localServerPath],
            usesUv: true,
            reason: 'local-checkout',
        };
    }
    return {
        command: uvPath,
        args: ['tool', 'run', 'visor-mcp'],
        usesUv: true,
        reason: 'uv-tool',
    };
}
