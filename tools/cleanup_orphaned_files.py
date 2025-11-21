#!/usr/bin/env python3
"""Storage orphan cleanup tool for Leyzen Vault.

This script identifies and removes files from disk that have no corresponding
database records. It provides a dry-run mode to preview changes before applying them.

Usage:
    # Copy script to container
    docker cp tools/cleanup_orphaned_files.py vault_web1:/tmp/

    # Execute in container
    docker exec -it vault_web1 python3 /tmp/cleanup_orphaned_files.py

    # Or directly
    docker exec -it vault_web1 python3 /app/tools/cleanup_orphaned_files.py

The script will:
1. Show a reconciliation report of orphaned files
2. Run a dry-run to show what would be deleted
3. Prompt for confirmation before actual cleanup
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vault.app import create_app
from vault.services.storage_reconciliation_service import StorageReconciliationService


def format_file_size(bytes_count: int) -> str:
    """Format bytes as human-readable size.

    Args:
        bytes_count: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def estimate_space_saved(storage, file_ids: set) -> int:
    """Estimate total size of files to be deleted.

    Args:
        storage: FileStorage instance
        file_ids: Set of file IDs to check

    Returns:
        Total size in bytes
    """
    total_size = 0
    for file_id in file_ids:
        try:
            file_path = storage.get_file_path(file_id)
            if file_path.exists():
                total_size += file_path.stat().st_size
        except Exception:
            pass  # Skip files we can't access
    return total_size


def main():
    """Run cleanup."""
    print("=" * 70)
    print("  Leyzen Vault - Storage Orphan Cleanup Tool")
    print("=" * 70)
    print()

    # Create app and get storage
    app = create_app()

    with app.app_context():
        storage = app.config.get("VAULT_STORAGE")
        if not storage:
            print("ERROR: Storage not configured!")
            sys.exit(1)

        reconciliation_service = StorageReconciliationService(storage)

        # Step 1: Show reconciliation report
        print("STEP 1: Storage Reconciliation Report")
        print("-" * 70)
        orphans = reconciliation_service.find_orphaned_files()

        print(f"Database records (active files): {orphans['db_records']}")
        print(f"Primary storage files (/data/files/): {orphans['primary_files']}")
        print(f"Source storage files (/data-source/files/): {orphans['source_files']}")
        print()
        print(f"Orphaned files in primary storage: {len(orphans['primary'])}")
        print(f"Orphaned files in source storage: {len(orphans['source'])}")
        print()

        if not orphans["primary"] and not orphans["source"]:
            print("✓ No orphaned files found! Storage is clean.")
            return

        # Estimate space to be saved
        primary_size = estimate_space_saved(storage, orphans["primary"])
        source_size = 0
        if storage.source_dir:
            # Estimate source size (approximate)
            source_size = estimate_space_saved(storage, orphans["source"])

        total_size = primary_size + source_size
        print(f"Estimated disk space to be freed:")
        print(f"  - Primary storage: {format_file_size(primary_size)}")
        if storage.source_dir:
            print(f"  - Source storage: {format_file_size(source_size)}")
        print(f"  - Total: {format_file_size(total_size)}")
        print()

        # Show sample of orphaned files (first 10)
        if orphans["primary"]:
            print("Sample orphaned files in primary storage (first 10):")
            for file_id in list(orphans["primary"])[:10]:
                print(f"  - {file_id}")
            if len(orphans["primary"]) > 10:
                print(f"  ... and {len(orphans['primary']) - 10} more")
            print()

        # Step 2: Dry run
        print()
        print("STEP 2: Dry Run (Preview)")
        print("-" * 70)
        dry_results = reconciliation_service.cleanup_orphaned_files(dry_run=True)

        print(
            f"Would delete from primary storage: {len(dry_results['deleted_primary'])} files"
        )
        print(
            f"Would delete from source storage: {len(dry_results['deleted_source'])} files"
        )
        print(
            f"Total files to delete: {len(dry_results['deleted_primary']) + len(dry_results['deleted_source'])}"
        )
        print()

        # Step 3: Confirm and execute
        print()
        print("STEP 3: Confirmation")
        print("-" * 70)
        print("⚠️  WARNING: This will permanently delete orphaned files from disk!")
        print("   This action cannot be undone.")
        print()

        response = input("Proceed with actual cleanup? Type 'yes' to continue: ")

        if response.lower() != "yes":
            print()
            print("Cleanup cancelled. No files were deleted.")
            return

        # Execute cleanup
        print()
        print("STEP 4: Executing Cleanup")
        print("-" * 70)
        results = reconciliation_service.cleanup_orphaned_files(dry_run=False)

        print(
            f"✓ Deleted from primary storage: {len(results['deleted_primary'])} files"
        )
        print(f"✓ Deleted from source storage: {len(results['deleted_source'])} files")
        print(
            f"✓ Total deleted: {len(results['deleted_primary']) + len(results['deleted_source'])} files"
        )

        if results["failed"]:
            print()
            print(f"⚠️  Failed to delete {len(results['failed'])} files:")
            for failure in results["failed"]:
                print(
                    f"  - {failure['file_id']} ({failure['location']}): {failure['error']}"
                )

        print()
        print("=" * 70)
        print("✓ Cleanup complete!")
        print("=" * 70)
        print()
        print("Summary:")
        print(
            f"  - Files deleted: {len(results['deleted_primary']) + len(results['deleted_source'])}"
        )
        print(f"  - Disk space freed: ~{format_file_size(total_size)}")
        print(f"  - Active files in database: {orphans['db_records']}")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("Cleanup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
