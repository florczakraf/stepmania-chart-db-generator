-- See SimplyLove-license.txt for a licensing information

-- Reduce the chart to it's smallest unique representable form.
local MinimizeChart = function(chartString)
	local function MinimizeMeasure(measure)
		local minimal = false
		-- We can potentially minimize the chart to get the most compressed
		-- form of the actual chart data.
		-- NOTE(teejusb): This can be more compressed than the data actually
		-- generated by StepMania. This is okay because the charts would still
		-- be considered equivalent.
		-- E.g. 0000                      0000
		--      0000  -- minimized to -->
		--      0000
		--      0000
		--      StepMania will always generate the former since quarter notes are
		--      the smallest quantization.
		while not minimal and #measure % 2 == 0 do
			-- If every other line is all 0s, we can minimize the measure.
			local allZeroes = true
			for i=2, #measure, 2 do
				-- Check if the row is NOT all zeroes (thus we can't minimize).
				if measure[i] ~= string.rep('0', measure[i]:len()) then
					allZeroes = false
					break
				end
			end

			if allZeroes then
				-- To remove every other element while keeping the
				-- indices valid, we iterate from [2, len(t)/2 + 1].
				-- See the example below (where len(t) == 6).

				-- index: 1 2 3 4 5 6  -> remove index 2
				-- value: a b a b a b

				-- index: 1 2 3 4 5    -> remove index 3
				-- value: a a b a b

				-- index: 1 2 3 4      -> remove index 4
				-- value: a a a b

				-- index: 1 2 3
				-- value: a a a
				for i=2, #measure/2+1 do
					table.remove(measure, i)
				end
			else
				minimal = true
			end
		end
	end

	local finalChartData = {}
	local curMeasure = {}
	for line in chartString:gmatch('[^\n]+') do
		-- If we hit a comma, that denotes the end of a measure.
		-- Try to minimize it, and then add it to the final chart data with
		-- the delimiter.
		-- Note: The ending semi-colon has been stripped out.
		if line == ',' then
			MinimizeMeasure(curMeasure)

			for row in ivalues(curMeasure) do
				table.insert(finalChartData, row)
			end
			table.insert(finalChartData, ',')
			-- Just keep removing the first element to clear the table.
			-- This way we don't need to wait for the GC to cleanup the unused values.
			for i=1, #curMeasure do
				table.remove(curMeasure, 1)
			end
		else
			table.insert(curMeasure, line)
		end
	end

	-- Add the final measure.
	if #curMeasure > 0 then
		MinimizeMeasure(curMeasure)

		for row in ivalues(curMeasure) do
			table.insert(finalChartData, row)
		end
	end

	return table.concat(finalChartData, '\n')
end

local NormalizeFloatDigits = function(param)
	local function NormalizeDecimal(decimal)
		-- Remove any control characters from the string to prevent conversion failures.
		decimal = decimal:gsub("%c", "")
		local rounded = tonumber(decimal)

		-- Round to 3 decimal places
		local mult = 10^3
		rounded = (rounded * mult + 0.5 - (rounded * mult + 0.5) % 1) / mult
		return string.format("%.3f", rounded)
	end

	local paramParts = {}
	for beat_bpm in param:gmatch('[^,]+') do
		local beat, bpm = beat_bpm:match('(.+)=(.+)')
		table.insert(paramParts, NormalizeDecimal(beat) .. '=' .. NormalizeDecimal(bpm))
	end
	return table.concat(paramParts, ',')
end

-- ----------------------------------------------------------------
-- ORIGINAL SOURCE: https://github.com/JonathanKnepp/SM5StreamParser

-- GetSimfileChartString() accepts four arguments:
--    SimfileString - the contents of the ssc or sm file as a string
--    StepsType     - a string like "dance-single" or "pump-double"
--    Difficulty    - a string like "Beginner" or "Challenge" or "Edit"
--    Filetype      - either "sm" or "ssc"
--
-- GetSimfileChartString() returns three values:
--    NoteDataString, a substring from SimfileString that contains the just the requested (minimized) note data
--    BPMs, a substring from SimfileString that contains the BPM string for this specific chart
--    DiffNumber, a number representing a numerical difficulty of the chart

local GetSimfileChartString = function(SimfileString, StepsType, Difficulty, StepsDescription, Filetype)
	local NoteDataString = nil
	local BPMs = nil
	local DiffNumber = nil

	-- ----------------------------------------------------------------
	-- StepMania uses each steps' "Description" attribute to uniquely
	-- identify Edit charts. (This is important, because there can be more
	-- than one Edit chart.)
	--
	-- SSC files use a dedicated #DESCRIPTION for this purpose
	-- SM files use the 3rd spot in the #NOTES field for this purpose
	-- ----------------------------------------------------------------

	if Filetype == "ssc" then
		local topLevelBpm = NormalizeFloatDigits(SimfileString:match("#BPMS:(.-);"):gsub("%s+", ""))
		-- SSC File
		-- Loop through each chart in the SSC file
		for noteData in SimfileString:gmatch("#NOTEDATA.-#NOTES2?:[^;]*") do
			-- Normalize all the line endings to '\n'
			local normalizedNoteData = noteData:gsub('\r\n?', '\n')

			-- WHY? Why does StepMania allow the same fields to be defined multiple times
			-- in a single NOTEDATA stanza.
			-- We'll just use the first non-empty one.
			-- TODO(teejsub): Double check the expected behavior even though it is
			-- currently sufficient for all ranked charts on GrooveStats.
			local stepsType = ''
			for st in normalizedNoteData:gmatch("#STEPSTYPE:(.-);") do
				if stepsType == '' and st ~= '' then
					stepsType = st
					break
				end
			end
			stepsType = stepsType:gsub("%s+", "")

			local difficulty = ''
			for diff in normalizedNoteData:gmatch("#DIFFICULTY:(.-);") do
				if difficulty == '' and diff ~= '' then
					difficulty = diff
					break
				end
			end
			difficulty = difficulty:gsub("%s+", "")

			local description = ''
			for desc in normalizedNoteData:gmatch("#DESCRIPTION:(.-);") do
				if description == '' and desc ~= '' then
					description = desc
					break
				end
			end

			local diffNumber = -1
			for meter in normalizedNoteData:gmatch("#METER:(.-);") do
				if diffNumber == -1 and meter ~= '' then
					diffNumber = tonumber(meter)
					break
				end
			end

			-- Find the chart that matches our difficulty and game type.
			if (stepsType == StepsType and difficulty == Difficulty) then
				-- Ensure that we've located the correct edit stepchart within the SSC file.
				-- There can be multiple Edit stepcharts but each is guaranteed to have a unique #DESCIPTION tag
				if (difficulty ~= "Edit" or description == StepsDescription) then
					-- Get chart specific BPMS (if any).
					local splitBpm = normalizedNoteData:match("#BPMS:(.-);") or ''
					splitBpm = splitBpm:gsub("%s+", "")

					if #splitBpm == 0 then
						BPMs = topLevelBpm
					else
						BPMs = NormalizeFloatDigits(splitBpm)
					end
					-- Get the chart data, remove comments, and then get rid of all non-'\n' whitespace.
					NoteDataString = normalizedNoteData:match("#NOTES2?:[\n]*([^;]*)\n?$"):gsub("//[^\n]*", ""):gsub('[\r\t\f\v ]+', '')
					NoteDataString = MinimizeChart(NoteDataString)

					DiffNumber = diffNumber

					break
				end
			end
		end
	elseif Filetype == "sm" then
		-- SM FILE
		BPMs = NormalizeFloatDigits(SimfileString:match("#BPMS:(.-);"):gsub("%s+", ""))
		-- Loop through each chart in the SM file
		for noteData in SimfileString:gmatch("#NOTES2?[^;]*") do
			-- Normalize all the line endings to '\n'
			local normalizedNoteData = noteData:gsub('\r\n?', '\n')
			-- Split the entire chart string into pieces on ":"
			local parts = {}
			for part in normalizedNoteData:gmatch("[^:]+") do
				parts[#parts+1] = part
			end

			-- The pieces table should contain at least 7 numerically indexed items
			-- 2, 4, (maybe 3) and 7 are the indices we care about for finding the correct chart
			-- Index 2 will contain the steps_type (like "dance-single")
			-- Index 4 will contain the difficulty (like "challenge")
			-- Index 3 will contain the description for Edit charts
			if #parts >= 7 then
				local stepsType = parts[2]:gsub("[^%w-]", "")
				local difficulty = parts[4]:gsub("[^%w]", "")
				local description = parts[3]:gsub("^%s*(.-)", "")
				local diffNumber = parts[5]:gsub("[^%d]", "")
				-- Find the chart that matches our difficulty and game type.
				if (stepsType == StepsType and difficulty == Difficulty) then
					-- Ensure that we've located the correct edit stepchart within the SSC file.
					-- There can be multiple Edit stepcharts but each is guaranteed to have a unique #DESCIPTION tag
					if (difficulty ~= "Edit" or description == StepsDescription) then
						NoteDataString = parts[7]:gsub("//[^\n]*", ""):gsub('[\r\t\f\v ]+', '')
						NoteDataString = MinimizeChart(NoteDataString)
						DiffNumber = tonumber(diffNumber)
						break
					end
				end
			end
		end
	end

	return NoteDataString, BPMs, DiffNumber
end

m = {}
function m.GetSimfileChartString(SimfileString, StepsType, Difficulty, StepsDescription, Filetype)
    return GetSimfileChartString(SimfileString, StepsType, Difficulty, StepsDescription, Filetype)
end
return m
