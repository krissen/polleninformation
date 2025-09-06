# Home Assistant: Pollen Information EU Integration

This is a Home Assistant custom component (HACS integration) that provides pollen information across Europe via the Austrian Pollen Information Service API.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Bootstrap and Setup
- **Ruff Installation Options:**
  - **PREFERRED**: System-wide install: `pip install --user ruff` (usually already available)
  - **ALTERNATIVE**: Virtual environment may timeout due to network issues
- **Python Environment:**
  - **NOT REQUIRED** for basic validation and linting
  - **NETWORK ISSUE**: `pip install -r requirements.txt` consistently fails with timeout errors on pypi.org
  - **WORKAROUND**: All basic development tasks work without virtual environment or additional dependencies
  - **Component works with system Python for validation, linting, and syntax checking**

### Build and Validation
- **Lint and Format**: `./scripts/lint.sh` -- takes <1 second. NEVER CANCEL.
  - Runs: `ruff format . && ruff check . --fix`
- **Syntax Validation**: `find custom_components/polleninformation -name "*.py" -exec python3 -m py_compile {} \;` -- takes <1 second
- **Translation Validation**: All JSON files validate successfully (16 language files)
- **Manifest Validation**: Basic validation passes (domain, name, version, documentation, issue_tracker present)

### No Traditional Build Process
- This is a Python Home Assistant integration - no compilation needed
- **DO NOT** attempt to build executables or run complex build systems
- **DO NOT** try to run Home Assistant server - requires full installation and configuration

## Validation

### Manual Validation Scenarios
- **ALWAYS** run `./scripts/lint.sh` before committing changes - CI will fail without it
- **ALWAYS** validate Python syntax with `python3 -m py_compile <modified-file.py>`
- **Translation Changes**: Only modify `custom_components/polleninformation/translations/en.json` per AGENTS.md
- **Manifest Changes**: Validate JSON with `python3 -c "import json; json.load(open('custom_components/polleninformation/manifest.json'))"`

### Component Structure Validation
- **Required Files**: All core component files exist (`__init__.py`, `sensor.py`, `config_flow.py`, etc.)
- **API Requirements**: Component requires API key from polleninformation.at (document this in setup instructions)
- **Dependencies**: Uses aiohttp, unidecode, voluptuous, async-timeout (defined in manifest.json)

### Testing Limitations
- **API Testing**: Requires valid API key from polleninformation.at - document this requirement
- **Script Testing**: `scripts/test_pollenapi.py` and similar require full dependencies - may fail due to network issues
- **Integration Testing**: Cannot run full Home Assistant without complete environment setup

## Common Tasks

### File Structure Overview
```
custom_components/polleninformation/
├── __init__.py          # Main integration setup
├── sensor.py            # Sensor platform implementation  
├── config_flow.py       # Configuration flow UI
├── api.py              # API communication layer
├── const.py            # Constants and configuration
├── utils.py            # Utility functions
├── manifest.json       # Integration metadata
├── translations/       # UI translations (16 languages)
└── *.png              # Icons and logos
```

### Key Scripts
```
scripts/
├── setup.sh            # Environment setup (requires python3.13 -> modify to python3)
├── dev_init.sh         # Development environment activation  
├── lint.sh             # Code formatting and linting
├── test_pollenapi.py   # API testing (requires dependencies)
└── README.md           # Script documentation
```

### Development Workflow
1. **Check Tools**: Verify `ruff --version` works (install with `pip install --user ruff` if needed)
2. **Make Changes**: Edit Python files in `custom_components/polleninformation/`
3. **Validate Syntax**: `python3 -m py_compile <changed-file.py>` -- takes <1 second
4. **Lint**: `./scripts/lint.sh` -- takes <1 second, NEVER CANCEL
5. **Validate Complete**: Full workflow takes <2 seconds total
6. **Commit**: Changes pass all validation steps

### API Integration Notes
- **Base URL**: `https://www.polleninformation.at/api/forecast/public`
- **Required Parameters**: country, lang, latitude, longitude, apikey
- **Supported Countries**: AT, CH, DE, ES, FR, GB, IT, LV, LT, PL, SE, TR, UA
- **Rate Limiting**: Respect API limits in testing scripts

## Critical Timing Information

| Command | Expected Time | Timeout Setting |
|---------|---------------|-----------------|
| `./scripts/lint.sh` | <1 second | Use default (no timeout needed) |
| `python3 -m py_compile` | <1 second | Use default |
| `ruff --version` | <1 second | Use default |
| Translation JSON validation | <1 second | Use default |
| Full validation workflow | <2 seconds | Use default |
| `pip install --user ruff` | ~30 seconds | Set timeout to 60 seconds |

**NEVER CANCEL**: All core development commands complete in under 2 seconds. Network operations consistently timeout due to infrastructure limitations - use system-wide package installation instead.

## Troubleshooting

### Network Issues
- **Symptom**: `pip install` consistently times out with "Read timed out" from pypi.org
- **Root Cause**: Infrastructure network limitations prevent virtual environment setup
- **Solution**: Use system-wide Python packages: `pip install --user ruff`
- **Impact**: All core development tasks work without virtual environments or additional dependencies

### API Testing
- **Requirement**: Valid API key from https://www.polleninformation.at/en/data-interface/request-an-api-key
- **Testing Scripts**: Located in `scripts/` but require full dependencies
- **Basic Testing**: Use syntax validation and linting instead of API calls

### Translation Updates
- **Rule**: Only modify `en.json` per project guidelines
- **Validation**: Ensure JSON remains valid after changes
- **Languages**: 16 supported languages, all maintain same structure

## Repository Context
- **Type**: Home Assistant Custom Component (HACS Integration)
- **Language**: Python 3.12+
- **License**: Per LICENSE.md
- **Documentation**: README.md, CONTRIBUTING.md
- **CI/CD**: GitHub Actions for HACS validation and linting