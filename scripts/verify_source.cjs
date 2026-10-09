// Parse source without executing it. Dependencies belong to the harness.
const fs = require('node:fs');
const path = require('node:path');
const parser = require('@babel/parser');
const ts = require('typescript');
const target = process.argv[2];
try {
  if (/\.tsx?$/.test(target)) {
    const configPath = ts.findConfigFile(path.dirname(target), ts.sys.fileExists);
    let options = { noEmit: true, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX };
    let files = [target];
    if (configPath) {
      const config = ts.readConfigFile(configPath, ts.sys.readFile);
      if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'));
      const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(configPath));
      if (parsed.errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(parsed.errors, {
        getCurrentDirectory: ts.sys.getCurrentDirectory, getCanonicalFileName: x => x, getNewLine: () => '\n'
      }));
      options = { ...parsed.options, noEmit: true };
      files = parsed.fileNames;
    }
    const program = ts.createProgram(files, options);
    const diagnostics = ts.getPreEmitDiagnostics(program);
    if (diagnostics.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCurrentDirectory: ts.sys.getCurrentDirectory, getCanonicalFileName: x => x, getNewLine: () => '\n'
    }));
  } else {
    parser.parse(fs.readFileSync(target, 'utf8'), {
      sourceType: 'unambiguous', plugins: ['jsx'], allowReturnOutsideFunction: false
    });
  }
  console.log('Source validation passed');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
