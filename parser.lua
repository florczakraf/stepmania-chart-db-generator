SL_ChartParser = require "SL-ChartParser"
json = require "json"
sha1 = require "sha1"
path = require "path"

-- from: stepmania / MIT / StepMania is (c) Chris Danford, the StepMania development team, et al. All rights reserved.
function ivalues(t)
    local n = 0
    return function()
        n = n + 1
        return t[n]
    end
end

-- based on: Simply Love / GPL3 / See SimplyLove-license.txt
local GetSimfileString = function(filename)
    if not filename or filename == "" then return end

    local filetype = filename:match("[^.]+$"):lower()
    if not (filetype=="ssc" or filetype=="sm") then return end

    local file = io.open(filename, "r")
    local contents = file:read("*all") 
    file:close()

    return contents, filetype
end

function save_chart_info(chart_info)
    os.execute("mkdir -p db/" .. chart_info["hash"]:sub(1, 2))
    local file = io.open("db/" .. chart_info["hash"]:sub(1, 2) .. "/" .. chart_info["hash"]:sub(3, -1) .. ".json", "w")
    file:write(json.encode(chart_info))
    file:close()
end

function main()
    -- skip Edits because they use some weird logic to match a chart
    local diffs = {"Beginner", "Easy", "Medium", "Hard", "Expert", "Challenge"}
    local steps_types = {"dance-single", "dance-double", "dance-solo", "dance-routine", "dance-couple"}
    
    local chart_string, file_type = GetSimfileString(arg[1])

    local title = chart_string:match("#TITLE:(.-);")
    local titletranslit = chart_string:match("#TITLETRANSLIT:(.);") or ""
    local subtitle = chart_string:match("#SUBTITLE:(.-);") or ""
    local subtitletranslit = chart_string:match("#SUBTITLETRANSLIT:(.);") or ""
    local artist = chart_string:match("#ARTIST:(.-);")
    local artisttranslit = chart_string:match("#ARTISTTRANSLIT:(.-);") or ""

    for diff in ivalues(diffs) do
        for steps_type in ivalues(steps_types) do
            notes, bpms = SL_ChartParser.GetSimfileChartString(chart_string, steps_type, diff, "", file_type)
            if notes and bpms then
                local hash = sha1.sha1(notes..bpms):sub(1, 16)
                local chart_info = {
                    title = title,
                    titletranslit = titletranslit,
                    subtitle = subtitle,
                    subtitletranslit = subtitletranslit,
                    artist = artist,
                    artisttranslit = artisttranslit,
                    bpms = bpms,
                    steps_type = steps_type,
                    diff = diff,
                    hash = hash,
                    directory = path.basename(path.dirname(arg[1])),
                    pack_name = path.basename(path.dirname(path.dirname(arg[1]))),
                }
                print(chart_info["directory"])
                print(chart_info["pack_name"])
                print(chart_info["hash"])
                print("----")
                save_chart_info(chart_info)
            end
        end
    end
end

main()
