# Reach probe evidence qualification

The retained reach/side/fine-body/thumb-fold candidate outputs were generated before the calibrated native_clearance classifier. Old nearest-triangle signed-normal tests can falsely reject points nearest an edge/corner, so their rejection counts are provisional and do not prove global impossibility. The exploratory thumb-fold probe checks only that thumb, not the whole tool/body. No full action is accepted by these candidate files.

The production prepared tool gates were rerun using native_clearance.py: see small-package-gripper/P03.5.3.2/native-contacts.json and clearance-calibration.json. The exploratory probe scripts now import the corrected classifier for future runs; retained older outputs have not been silently relabelled as new results.
