This component writes data from Keboola Connection to [Helios Nephrite](https://www.helios.eu/en/), a modern ERP system designed for medium and large enterprises.

## Features

- **Entity Creation**: Create records for any entity type available in your Helios Nephrite instance (e.g., customers, products, invoices, orders).
- **Flexible Field Mapping**: Map columns from your input CSV to Helios entity fields with an intuitive UI that auto-suggests mappings based on column name matching.
- **Folder Organization**: Target specific folders within Helios to organize your data according to your business structure.
- **Batch Processing**: Process multiple input tables in a single run, efficiently creating entities row by row.

## Configuration

1. **Connection Settings**: Provide your Helios API URL, username, and password. Optionally set a default folder ID for data organization.
2. **Entity Selection**: Choose the target entity type (e.g., `Adresar` for address book, `Zbozi` for products).
3. **Field Mapping**: Use the "Load Fields" button to fetch available entity fields and configure the mapping from your CSV columns to Helios fields.

## Use Cases

- Synchronize customer master data from external systems into Helios
- Import product catalogs and inventory data
- Load transactional data such as orders or invoices
- Migrate data from legacy systems to Helios Nephrite

## Notes

- Ensure your Helios user account has appropriate permissions to create entities in the target folders.
- The component creates new records only; updating existing records is not supported in this version.
- Empty values in mapped columns are sent as null to the API.