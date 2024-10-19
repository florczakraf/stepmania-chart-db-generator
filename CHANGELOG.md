# Changelog

## [Unreleased](https://github.com/florczakraf/stepmania-chart-db-generator/compare/v2.1.0...HEAD)
### Added
- Added bandit, isort and pre-commit
- Added GitHub pipeline to enforce static code analysis

### Changed
- Fixed issues reported by bandit (sha1 with `usedforsecurity=False` and too broad `except` clause)

## [v2.1.0] 2024-10-17

### Added
- New `lazy` DB driver has been added to improve extending big databases which is
the default use-case. DB driver can be manually changed with `--db-driver` option.

### Changed
- Missing `last_update` has been implemented for `inmem` DB driver


## [v2.0.0] 2024-10-16
Initial release of the version 2. Project has been recreated in python for
improved parsing capabilities and speed. See README.md for the format
specification.


[v2.1.0]: https://github.com/florczakraf/stepmania-chart-db-generator/compare/v2.0.0...v2.1.0
[v2.0.0]: https://github.com/florczakraf/stepmania-chart-db-generator/tree/v2.0.0
