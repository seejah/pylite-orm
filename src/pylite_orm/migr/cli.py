import argparse, sys, sqlite3, tomllib
from datetime import datetime
from pathlib import Path

def find_toml():
    current = Path.cwd()
    for p in [current] + list(current.parents):
        if (p / 'migrate.toml').exists():
            return p / 'migrate.toml'
    return None

def load_config(toml_path: Path) -> dict:
    with open(toml_path, 'rb') as f:
        return tomllib.load(f)

def cmd_init(args):
    toml_path = Path.cwd() / 'migrate.toml'
    if toml_path.exists():
        print('当前目录已存在 migrate.toml')
        return
    default_db = args.db or './app.db'
    default_dir = args.dir or './migrations'
    
    content = f'''[migrate]
db_path = "{default_db}"
migrations_dir = "{default_dir}"
models_dir = "./models"
'''
    toml_path.write_text(content, encoding='utf-8')
    Path(default_dir).mkdir(parents=True, exist_ok=True)
    print(f'✅ Migration configuration successfully: {toml_path}')

def cmd_create(args):
    toml_path = find_toml()
    if not toml_path:
        print('❌ migrate.toml not found. Please run "lite-migr" init in the project root directory first.')
        sys.exit(1)
        
    config = load_config(toml_path)['migrate']
    migrations_dir = Path(config['migrations_dir'])
    migrations_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = config.get('db_path', './app.db')
    models_dir = config.get('models_dir')
    
    if not models_dir:
        print('❌ Error: "models_dir" must be configured in migrate.toml for automatic generation.')
        sys.exit(1)

    print(f'🔍 Analyzing differences between models and database....')
    
    db_exists = Path(db_path).exists()
    conn = sqlite3.connect(db_path) if db_exists else sqlite3.connect(':memory:')
    try:
        from .inspector import get_db_schema, get_model_schema
        from .diff import calculate_diff
        from .generator import render_migration_code

        db_schema = get_db_schema(conn)
        model_schema = get_model_schema(models_dir)
        #print('模型结构', model_schema, '\n数据库结构', db_schema)
        ops = calculate_diff(db_schema, model_schema)
        
        warnings = []
        if not db_exists:
            warnings.append('Database file does not exist; full table creation SQL will be generated.')            
        if not ops:
            print('✅ The database structure is completely consistent with the model; no migration files need to be generated.')
            return
        code = render_migration_code(ops, warnings)
    except Exception as e:
        print(f'❌ Error occurred while analyzing differences: {e}')
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{args.name}.py"
    filepath = migrations_dir / filename
    
    filepath.write_text(code, encoding='utf-8')
    print(f'✅ Migration file created successfully: {filepath}')

def cmd_upgrade(args):
    toml_path = find_toml()
    if not toml_path:
        print('❌ Error: migrate.toml not fonnd')
        sys.exit(1)
    config = load_config(toml_path)['migrate']
    
    from .runner import MigrationRunner
    runner = MigrationRunner(config['db_path'], config['migrations_dir'])
    runner.upgrade()

def main():
    parser = argparse.ArgumentParser(prog='lite-migr', description='LiteORM Database Synchronization & Migration Tool')
    subparsers = parser.add_subparsers(dest="command")

    p_init = subparsers.add_parser('init', help="Initialize migration configuration file migrate.toml")
    p_init.add_argument('--db', help='Specify database path')
    p_init.add_argument('--dir', help='Specify migrations directory path')

    p_create = subparsers.add_parser('create', help='Create migration script based on model differences')
    p_create.add_argument('name', help='Migration name (e.g. sync_user_model)')

    subparsers.add_parser('upgrade', help='Apply pending migrations to synchronize database structure')

    args = parser.parse_args()
    if args.command == 'init': cmd_init(args)
    elif args.command == 'create': cmd_create(args)
    elif args.command == 'upgrade': cmd_upgrade(args)
    else: parser.print_help()

if __name__ == '__main__':
    main()