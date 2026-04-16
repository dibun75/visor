const esbuild = require('esbuild');

esbuild.build({
    entryPoints: ['./src/extension.ts'],
    bundle: true,
    outfile: './out/extension.js',
    external: ['vscode'],
    format: 'cjs',
    platform: 'node',
    target: 'node18',
    sourcemap: false,
    minify: false,
}).then(() => {
    console.log('Build complete');
}).catch((e) => {
    console.error(e);
    process.exit(1);
});
