Helios Nephrite Writer
=============

**Please contact Keboola support to assist with the initial setup of this component.**

Description
-----------

This component writes data from Keboola Connection to [Helios Nephrite](https://www.helios.eu/en/), a modern ERP system designed for medium and large enterprises.

Helios is a comprehensive ERP system for enterprise resource planning, offering modules for finance, accounting, inventory, sales, purchasing, and business process management.

**Table of Contents:**

[TOC]

Features
========

| **Feature**             | **Description**                                                                                     |
|-------------------------|-----------------------------------------------------------------------------------------------------|
| Entity Creation         | Create records for any entity type available in your Helios Nephrite instance.                      |
| Flexible Field Mapping  | Map columns from your input CSV to Helios entity fields with auto-suggested mappings.               |
| Folder Organization     | Target specific folders within Helios to organize your data according to your business structure.   |
| Batch Processing        | Process multiple input tables in a single run, efficiently creating entities row by row.            |

Use Cases
=========

- Synchronize customer master data from external systems into Helios
- Import product catalogs and inventory data
- Load transactional data such as orders or invoices
- Migrate data from legacy systems to Helios Nephrite

Configuration
=============

Connection Settings
-------------------

| Parameter           | Description                                                        | Required |
|---------------------|--------------------------------------------------------------------|----------|
| API URL             | The base URL of your Helios Nephrite API instance.                 | Yes      |
| Username            | Your Helios account username.                                      | Yes      |
| Password            | Your Helios account password.                                      | Yes      |
| Default Folder ID   | Optional default folder ID for organizing created entities.        | No       |

Entity Settings
---------------

| Parameter      | Description                                                                                      | Required |
|----------------|--------------------------------------------------------------------------------------------------|----------|
| Entity Name    | The target entity type in Helios (e.g., `Adresar` for address book, `Zbozi` for products).       | Yes      |
| Folder ID      | Override the default folder ID for this specific configuration.                                  | No       |
| Field Mapping  | Mapping of source CSV columns to destination Helios entity fields. Use "Load Fields" to configure. | Yes      |

Notes
=====

- Ensure your Helios user account has appropriate permissions to create entities in the target folders.
- The component creates new records only; updating existing records is not supported in this version.
- Empty values in mapped columns are sent as null to the API.

Development
-----------

To customize the local data folder path, replace the `CUSTOM_FOLDER` placeholder with your desired path in the `docker-compose.yml` file:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone this repository, initialize the workspace, and run the component using the following
commands:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
git clone https://github.com/keboola/component-wr-helios-nephrite component-helios-nephrite-writer
cd component-helios-nephrite-writer
docker-compose build
docker-compose run --rm dev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the test suite and perform lint checks using this command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose run --rm test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration
===========

For details about deployment and integration with Keboola, refer to the
[deployment section of the developer
documentation](https://developers.keboola.com/extend/component/deployment/).