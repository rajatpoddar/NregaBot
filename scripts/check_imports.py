#!/usr/bin/env python3
"""
Comprehensive import checker - tests every Python file in the project.
"""
import os
import sys
import importlib
import traceback

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

errors = []
success = []
syntax_errors = []

# Collect all Python files excluding backups, venv, __pycache__
all_files = []
for root_dir, dirs, files in os.walk('.'):
    # Skip excluded dirs (dist/build = PyInstaller output bundles — unke andar
    # ki site-packages copies scan karna 855 false 'No module named dist...'
    # errors deta tha; wo real source errors ka signal drown kar dete hain).
    dirs[:] = [d for d in dirs if d not in ('__pycache__', 'venv', 'backups', '.git', '.github', 'tabs_backup_c7', 'nrega-server', 'tests', 'dist', 'build')]
    for f in files:
        if f.endswith('.py'):
            full_path = os.path.join(root_dir, f)
            all_files.append(full_path)

print(f'Found {len(all_files)} Python files to check')
print('=' * 70)

for filepath in sorted(all_files):
    rel_path = os.path.relpath(filepath, project_root).replace('\\', '/')
    
    # Skip __init__ files for import test (they're loaded automatically)
    if os.path.basename(filepath) == '__init__.py':
        continue
    
    # Convert path to module name
    mod_parts = rel_path.replace('.py', '').split('/')
    mod_name = '.'.join(mod_parts)
    
    # Skip scripts/ files that aren't part of the main package
    if mod_name.startswith('scripts.'):
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
        compile(source, filepath, 'exec')
    except SyntaxError as e:
        syntax_errors.append((rel_path, str(e)))
        print(f'SYNTAX ERROR: {rel_path}')
        print(f'  Line {e.lineno}: {e.msg}')
        print()
        continue
    
    try:
        importlib.import_module(mod_name)
        success.append(rel_path)
    except ImportError as e:
        errors.append((rel_path, str(e)))
        print(f'IMPORT ERROR: {rel_path}')
        print(f'  Cause: {e}')
    except Exception as e:
        errors.append((rel_path, f'{type(e).__name__}: {str(e)[:200]}'))
        print(f'RUNTIME ERROR: {rel_path}')
        print(f'  Cause: {type(e).__name__}: {str(e)[:200]}')

print('=' * 70)
print(f'Results: {len(success)} OK, {len(errors)} ERRORS, {len(syntax_errors)} SYNTAX ERRORS')

if errors:
    print('\nIMPORT/RUNTIME ERRORS:')
    for path, err in errors:
        print(f'  [{path}] {err}')

if syntax_errors:
    print('\nSYNTAX ERRORS:')
    for path, err in syntax_errors:
        print(f'  [{path}] {err}')

# Save results to file
with open('docs/import_check_results.txt', 'w') as f:
    f.write(f'Results: {len(success)} OK, {len(errors)} ERRORS, {len(syntax_errors)} SYNTAX ERRORS\n\n')
    if errors:
        f.write('IMPORT/RUNTIME ERRORS:\n')
        for path, err in errors:
            f.write(f'  [{path}] {err}\n')
    if syntax_errors:
        f.write('\nSYNTAX ERRORS:\n')
        for path, err in syntax_errors:
            f.write(f'  [{path}] {err}\n')
    if not errors and not syntax_errors:
        f.write('All imports passed!')

print('\nResults saved to docs/import_check_results.txt')
