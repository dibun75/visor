import { test } from 'node:test';
import * as assert from 'node:assert/strict';
import {
    augmentedPath,
    chooseServerLaunch,
    resolveUvPath,
    uvCandidatePaths,
} from '../launch';

const workspace = '/work/project';
const uvPath = '/home/dev/.local/bin/uv';

// --- server launch choices (issue #69) ---

test('a configured server.py is launched with uv run', () => {
    const plan = chooseServerLaunch({
        uvPath,
        workspaceFolder: workspace,
        customServerPath: '/opt/visor/src/visor/server.py',
        localServerExists: false,
        localServerPath: `${workspace}/src/visor/server.py`,
    });
    assert.equal(plan.command, uvPath);
    assert.deepEqual(plan.args, [
        '--directory', workspace, 'run', '-q', '/opt/visor/src/visor/server.py',
    ]);
    assert.equal(plan.usesUv, true);
});

test('a configured executable is launched directly without uv', () => {
    const plan = chooseServerLaunch({
        uvPath,
        workspaceFolder: workspace,
        customServerPath: '/usr/local/bin/visor-mcp',
        // Even with a local checkout, the configured executable wins.
        localServerExists: true,
        localServerPath: `${workspace}/src/visor/server.py`,
    });
    assert.equal(plan.command, '/usr/local/bin/visor-mcp');
    assert.deepEqual(plan.args, []);
    assert.equal(plan.usesUv, false);
});

test('a workspace with src/visor/server.py runs the local checkout', () => {
    const plan = chooseServerLaunch({
        uvPath,
        workspaceFolder: workspace,
        localServerExists: true,
        localServerPath: `${workspace}/src/visor/server.py`,
    });
    assert.equal(plan.command, uvPath);
    assert.deepEqual(plan.args, [
        '--directory', workspace, 'run', '-q', `${workspace}/src/visor/server.py`,
    ]);
    assert.equal(plan.usesUv, true);
});

test('an ordinary workspace uses uv tool run visor-mcp', () => {
    for (const customServerPath of [undefined, '']) {
        const plan = chooseServerLaunch({
            uvPath,
            workspaceFolder: workspace,
            customServerPath,
            localServerExists: false,
            localServerPath: `${workspace}/src/visor/server.py`,
        });
        assert.equal(plan.command, uvPath);
        assert.deepEqual(plan.args, ['tool', 'run', 'visor-mcp']);
        assert.equal(plan.usesUv, true);
    }
});

// --- uv lookup (issue #73) ---

const winHost = {
    platform: 'win32' as NodeJS.Platform,
    env: {
        USERPROFILE: 'C:\\Users\\dev',
        LOCALAPPDATA: 'C:\\Users\\dev\\AppData\\Local',
        ProgramData: 'C:\\ProgramData',
        Path: 'C:\\Windows\\System32',
    },
};

const linuxHost = {
    platform: 'linux' as NodeJS.Platform,
    env: { HOME: '/home/dev', PATH: '/usr/bin:/bin' },
};

test('Windows candidates include the usual uv install locations', () => {
    const candidates = uvCandidatePaths(winHost);
    for (const expected of [
        'C:\\Users\\dev\\.local\\bin\\uv.exe',
        'C:\\Users\\dev\\.cargo\\bin\\uv.exe',
        'C:\\Users\\dev\\scoop\\shims\\uv.exe',
        'C:\\Users\\dev\\AppData\\Local\\Microsoft\\WinGet\\Links\\uv.exe',
        'C:\\ProgramData\\chocolatey\\bin\\uv.exe',
    ]) {
        assert.ok(candidates.includes(expected), `missing ${expected}`);
    }
    assert.ok(candidates.every((c) => c.endsWith('uv.exe')));
});

test('Unix candidates keep the existing lookup locations', () => {
    const candidates = uvCandidatePaths(linuxHost);
    for (const expected of [
        '/home/dev/.local/bin/uv',
        '/home/dev/.cargo/bin/uv',
        '/usr/local/bin/uv',
        '/usr/bin/uv',
    ]) {
        assert.ok(candidates.includes(expected), `missing ${expected}`);
    }
    assert.ok(candidates.indexOf('/home/dev/.local/bin/uv') < candidates.indexOf('/usr/bin/uv'));
});

test('UV_INSTALL_DIR is checked first', () => {
    const candidates = uvCandidatePaths({
        platform: 'win32',
        env: { ...winHost.env, UV_INSTALL_DIR: 'D:\\tools\\uv' },
    });
    assert.equal(candidates[0], 'D:\\tools\\uv\\uv.exe');
});

test('augmented PATH uses the platform separator', () => {
    const win = augmentedPath(winHost);
    assert.ok(win.split(';').includes('C:\\Users\\dev\\.local\\bin'));
    assert.ok(win.endsWith(';C:\\Windows\\System32'));
    const unix = augmentedPath(linuxHost);
    assert.ok(unix.split(':').includes('/home/dev/.local/bin'));
    assert.ok(unix.endsWith(':/usr/bin:/bin'));
});

test('Windows lookup uses where and takes the first match', () => {
    const calls: string[] = [];
    const found = resolveUvPath(winHost, {
        exists: (f) => f === 'C:\\Users\\dev\\.local\\bin\\uv.exe',
        lookup: (command, args) => {
            calls.push([command, ...args].join(' '));
            return 'C:\\Users\\dev\\.local\\bin\\uv.exe\r\nC:\\other\\uv.exe\r\n';
        },
    });
    assert.deepEqual(calls, ['where uv']);
    assert.equal(found, 'C:\\Users\\dev\\.local\\bin\\uv.exe');
});

test('Windows falls back to known locations when where fails', () => {
    const found = resolveUvPath(winHost, {
        exists: (f) => f === 'C:\\Users\\dev\\AppData\\Local\\Microsoft\\WinGet\\Links\\uv.exe',
        lookup: () => { throw new Error('not found'); },
    });
    assert.equal(found, 'C:\\Users\\dev\\AppData\\Local\\Microsoft\\WinGet\\Links\\uv.exe');
});

test('Unix lookup still uses which, then candidates, then bare uv', () => {
    const calls: string[] = [];
    const viaWhich = resolveUvPath(linuxHost, {
        exists: (f) => f === '/usr/local/bin/uv',
        lookup: (command) => { calls.push(command); return '/usr/local/bin/uv\n'; },
    });
    assert.deepEqual(calls, ['which']);
    assert.equal(viaWhich, '/usr/local/bin/uv');

    const viaCandidate = resolveUvPath(linuxHost, {
        exists: (f) => f === '/home/dev/.cargo/bin/uv',
        lookup: () => { throw new Error('no which'); },
    });
    assert.equal(viaCandidate, '/home/dev/.cargo/bin/uv');

    const bare = resolveUvPath(linuxHost, {
        exists: () => false,
        lookup: () => { throw new Error('no which'); },
    });
    assert.equal(bare, 'uv');
});
