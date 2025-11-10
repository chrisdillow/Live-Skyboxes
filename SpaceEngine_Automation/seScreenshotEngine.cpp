//SpaceEngine Screenshot Engine
//Engine
//Chris D. | Version 1 | Version Date: 11/9/2025

// ============================================================ //
// |                    VERSION HISTORY                       | //
// ============================================================ //
//Version 0 (10/29/2025): Functional launch
//Version 1 (11/9/2025): Reprogramming from Python to C++ for
//  performance.

// ============================================================ //
// |                  PROGRAM DESCRIPTION                     | //
// ============================================================ //
//Takes user inputs from the UI to generate the proper code for
//automating panoramic skybox frame screenshotting in SpaceEngine.

// ============================================================ //
// |                  COMPILE BASH SCRIPT                     | //
// ============================================================ //
// g++ -std=c++17 -O2 seScreenshotEngine.cpp -o seScreenshotEngine

// ============================================================ //
// |                    INCLUDE / DEFINE                      | //
// ============================================================ //

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <filesystem>

namespace fs = std::filesystem;

// ============================================================ //
// |             FUNCTION AND STRUCT DEFINITIONS              | //
// ============================================================ //
// --------------------- TIME ADVANCEMENT --------------------- //
struct CalendarSpec {
    double dayHours {24.0}; //Length of 1 day in Earth hours
    double monthDays {30.0}; //Length of 1 month in planet-days
    double yearDays {365.0}; //Length of 1 year in planet-days
    int year0 {2000}; //Base year (YYYY label origin)
};

struct DateParts {
    int year{2000}, month{1}, day{1}, hour{0}, minute{0};
    double second{0.0};
};

struct PlanetClock {
    CalendarSpec spec;
    
    double daySec() const {
        return spec.dayHours * 3600.0;
    }
    double monthSec() const {
        return spec.monthDays * daySec();
    }
    double yearSec() const {
        return spec.yearDays * daySec();
    }

    double toSeconds(const DateParts& part) const {
        int yearOffset = part.year - spec.year0;
        //Month index is (month - 1) | Day index is (day - 1)
        double time = 0.0;
        time += yearOffset * yearSec();
        time += (part.month - 1) * monthSec();
        time += (part.day - 1) * daySec();
        time += part.hour * 3600.0;
        time += part.minute * 60.0;
        time += part.second;
        return time;
    }

    DateParts fromSeconds(double seconds) const {
        DateParts part;
        // ----- Years ----- //
        double years = std::floor(seconds / yearSec());
        seconds -= years * yearSec();
        part.year = spec.year0 + static_cast<int>(years);

        // ----- Months ----- //
        double months = std::floor(seconds / monthSec());
        seconds -= months * monthSec();
        part.month = static_cast<int>(months) + 1;

        // ------ Days ----- //
        double days = std::floor(seconds / daySec());
        seconds -= days * daySec();
        part.day = static_cast<int>(days) + 1;

        // ----- Time of Day ----- //
        part.hour = static_cast<int>(std::floor(seconds / 3600.0));
        seconds -= part.hour * 3600.0;
        part.minute = static_cast<int>(std::floor(seconds / 60.0));
        seconds -= part.minute * 60.0;
        part.second = seconds;

        return part;
    }
    // ============= FORMATTING FOR SPACEENGINE ============== //
    static std::string formatDate(const DateParts& part) {
        char buffer[32];
        std::snprintf(buffer,sizeof(buffer),"%04d.%02d.%02d",part.year,part.month,part.day);
        return std::string(buffer);
    }

    static std::string formatTime(const DateParts& part) {
        char buffer[32];
        std::snprintf(buffer,sizeof(buffer),"%02d:%02d:%05.2f",part.hour,part.minute,part.second);
        return std::string(buffer);
    }

    // -- Parsing "YYYY.MM.DD" and "HH:MM:SS.ss" into parts -- //
    static DateParts parseParts(const std::string& ymd,const std::string& hms,int year0default) {
        DateParts part;
        int year = year0default, month = 1, day = 1, hour = 0, minute = 0;
        double second = 0.0;
        std::sscanf(ymd.c_str(),"%d.%d.%d",&year,&month,&day);
        std::sscanf(hms.c_str(),"%d:%d:%lf",&hour,&minute,&second);
        part.year = year;
        part.month = month;
        part.day = day;
        part.hour = hour;
        part.minute = minute;
        part.second = second;
        return part;
    }
    // --------------- Time Stepping Utilities --------------- //
    double addSeconds(double time,double seconds) const {
        return time + seconds;
    }
    
    double addHours(double time,double hours) const {
        return time + hours * 3600.0;
    }

    double addDays(double time,double days) const {
        return time + days * daySec();
    }

    double addMonths(double time,double months) const {
        return time + months * monthSec();
    }

    double addYears(double time,double years) const {
        return time + years * yearSec();
    }
    // ------------------ Time Comparisons ------------------- //
    static bool greaterThanOrEqualTo(double time1,double time2) {
        return (time1 + 1e-9) >= time2;
    }
};

// ------------------------ HANDLING ------------------------- //
static void usage(const char* argv0) {
    std::fprintf(stderr,
    "Usage:\n"
        "  %s --out <path/to/adaptiveSkybox.se>\n"
        "     --scriptName <name>\n"
        "     --capturePosition <id_or_path>\n"
        "     --initialDate YYYY.MM.DD\n"
        "     --captureObject <name>\n"
        "     --captureType <CubeMap|FishEye|...>\n"
        "     --exportFiletype <jpg|png|dds|tif|tga>\n"
        "     --frames N\n"
        "     [--startTime HH:MM:SS.ss]\n"
        "     [--preDisplay <mode>] [--preDate YYYY.MM.DD] [--preTime HH:MM:SS.ss]\n"
        "     --dayHours <double>\n"
        "     --monthDays <double>\n"
        "     --yearDays <double>\n"
        "     [--year0 <int>]\n"
        "     --intervalUnit <seconds|hours|days|months|years>\n"
        "     --intervalStep <double>\n"
        "     [--endDate YYYY.MM.DD] [--endTime HH:MM:SS.ss]\n"
        "     [--orbitPeriodHours <double>]\n"
        "     [--debugDir <folder>] (writes a .txt copy for debugging)\n",
        argv0);
}

static std::string getArg(int& i,int argc,char** argv) {
    if (i + 1 >= argc) {
        throw std::runtime_error(std::string("Missing value after ") + argv[i]);
    }
    return std::string(argv[++i]);
}

// ============================================================ //
// |                      MAIN PROGRAM                        | //
// ============================================================ //
int main(int argc,char** argv) {
    try {
        if (argc == 1) {
            usage(argv[0]);
            return 1;
        }

        // ===================== INPUTS ===================== //
        std::string outPath;
        std::string scriptName = "LIVE SKYBOXES";
        std::string capturePosition;
        std::string initialDate; //Format YYYY.MM.DD
        std::string startTime = "00:00:00.00";
        std::string captureObject;
        std::string captureType;
        std::string exportFiletype;
        int frames = 0;
        std::string debugDir;

        //NOTE: Below are all default parameters
        std::string preDisplay = "Planetarium"; //TODO: Determine if this is a proper display to default to
        std::string preDate = "2000.01.01";
        std::string preTime = "00:00:00.00";

        // ----- Calculatable Parameters ----- //
        CalendarSpec planetCalendar;
        std::string intervalUnit = "days";
        double intervalStep = 1.0;
        // --- Optional Hardstops --- //
        std::string endDate;
        std::string endTime = "00:00:00.00";
        double orbitPeriodHours = 0.0;

        for (int i = 1;i < argc; ++i) {
            std::string key = argv[i];
            if (key == "--out") {
                outPath = getArg(i,argc,argv);
            } else if (key == "--scriptName") {
                scriptName = getArg(i,argc,argv);
            } else if (key == "--capturePosition") {
                capturePosition = getArg(i,argc,argv);
            } else if (key == "--initialDate") {
                initialDate = getArg(i,argc,argv);
            } else if (key == "--startTime") {
                startTime = getArg(i,argc,argv);
            } else if (key == "--captureObject") {
                captureObject = getArg(i,argc,argv);
            } else if (key == "--captureType") {
                captureType = getArg(i,argc,argv);
            } else if (key == "--exportFiletype") {
                exportFiletype = getArg(i,argc,argv);
            } else if (key == "--frames") {
                frames = std::stoi(getArg(i,argc,argv));
            } else if (key == "--preDisplay") {
                preDisplay = getArg(i,argc,argv);
            } else if (key == "--preDate") {
                preDate = getArg(i,argc,argv);
            } else if (key == "--preTime") {
                preTime = getArg(i,argc,argv);
            } else if (key == "--dayHours") {
                planetCalendar.dayHours = std::stod(getArg(i,argc,argv));
            } else if (key == "--monthDays") {
                planetCalendar.monthDays = std::stod(getArg(i,argc,argv));
            } else if (key == "--yearDays") {
                planetCalendar.yearDays = std::stod(getArg(i,argc,argv));
            } else if (key == "--year0") {
                planetCalendar.year0 = std::stoi(getArg(i,argc,argv));
            } else if (key == "--intervalUnit") {
                intervalUnit = getArg(i,argc,argv);
            } else if (key == "--intervalStep") {
                intervalStep = std::stod(getArg(i,argc,argv));
            } else if (key == "--endDate") {
                endDate = getArg(i,argc,argv);
            } else if (key == "--endTime") {
                endTime = getArg(i,argc,argv);
            } else if (key == "--orbitPeriodHours") {
                orbitPeriodHours = std::stod(getArg(i,argc,argv));
            } else if (key == "--debugDir") {
                debugDir = getArg(i,argc,argv);
            } else {
                usage(argv[0]);
                throw std::runtime_error("Unknown argument: "  + key);
            }
        }

        PlanetClock planetClock{planetCalendar};

        if (frames <= 0) {
            if (orbitPeriodHours > 0.0) {
                // Compute frames from orbit period
                double stepHours = 0.0;
                if      (intervalUnit == "seconds") stepHours = intervalStep / 3600.0;
                else if (intervalUnit == "hours")   stepHours = intervalStep;
                else if (intervalUnit == "days")    stepHours = intervalStep * planetCalendar.dayHours;
                else if (intervalUnit == "months")  stepHours = intervalStep * planetCalendar.monthDays * planetCalendar.dayHours;
                else if (intervalUnit == "years")   stepHours = intervalStep * planetCalendar.yearDays  * planetCalendar.dayHours;
                else throw std::runtime_error("Unknown intervalUnit: " + intervalUnit);

                if (stepHours <= 0.0)
                    throw std::runtime_error("intervalStep must be > 0");

                frames = (int)std::ceil(orbitPeriodHours / stepHours);
                if (frames < 1) frames = 1;
            }
            else if (!endDate.empty()) {
                // Compute frames by stepping until we reach/past end date/time
                DateParts startParts = PlanetClock::parseParts(initialDate, startTime, planetCalendar.year0);
                DateParts endParts   = PlanetClock::parseParts(endDate,   endTime,   planetCalendar.year0);

                double time    = planetClock.toSeconds(startParts);
                double timeEnd = planetClock.toSeconds(endParts);

                int count = 0;

                if (intervalStep <= 0.0) {
                    throw std::runtime_error("intervalStep must be > 0 when deriving frames from endDate or endTime");
                }

                while (true) {
                ++count;
                if      (intervalUnit == "seconds") time = planetClock.addSeconds(time, intervalStep);
                else if (intervalUnit == "hours")   time = planetClock.addHours  (time, intervalStep);
                else if (intervalUnit == "days")    time = planetClock.addDays   (time, intervalStep);
                else if (intervalUnit == "months")  time = planetClock.addMonths (time, intervalStep);
                else if (intervalUnit == "years")   time = planetClock.addYears  (time, intervalStep);
                else throw std::runtime_error("Unknown intervalUnit: " + intervalUnit);

            if (PlanetClock::greaterThanOrEqualTo(time, timeEnd))
                break;
            }
            frames = count;
        }
        else {
            throw std::runtime_error("Either --frames or --orbitPeriodHours or --endDate/--endTime is required.");
        }
    }
        if (outPath.size() < 3 || outPath.substr(outPath.size() - 3) != ".se") {
            outPath += ".se";
        }

        if (outPath.empty() || capturePosition.empty() || initialDate.empty()
            || captureObject.empty() || captureType.empty() || exportFiletype.empty()
            || frames <= 0) {
                usage(argv[0]);
                throw std::runtime_error("Missing required arguments.");
            }
        // ================ SE FILE TEMPLATES ================ //
        //PREPARATION from screenshotSetup
        auto screenshotSetup = [&](const std::string& initialDateStr) {
            std::ostringstream ss;
            ss
            << "Print \"[" << scriptName << "] Preparing screenshot configuration.\"\n"
            << "Select " << capturePosition << "\n"
            << "Goto {Time 2.0 Dist 0.001}\n"
            << "Center\n"
            << "StopTime\n"
            << "Date \"" << initialDateStr << " 00:00:00.00\"\n"
            << "Hide " << captureObject << "\n"
            << "DisplayMode \"" << captureType << "\"\n"
            << "HidePrint\n"
            << "WaitMessage \"[" << scriptName << "] Screenshot preparation complete. Press [NEXT] when you are ready to begin the export.\"\n";
            return ss.str();
        };

        // ==================== EXECUTION ==================== //
        auto frameBlock = [&](int frameNum,int frameTotal,
                        const std::string& curDate,const std::string& curTime,
                        const std::string& nextDate,const std::string& nextTime) {
                            std::ostringstream ss;
                            ss
                            << "Print \"[" << scriptName << "] Creating frame " << frameNum << " of " << frameTotal << ".\"\n"
                            << "Date \"" << curDate << " " << curTime << "\"\n"
                            << "Screenshot {Format \"" << exportFiletype << "\" Name \"frame_\"}\n"
                            << "Date \"" << nextDate << " " << nextTime << "\"\n"
                            << "HidePrint\n";
                            return ss.str();
                        };
        auto restore = [&]() {
            std::ostringstream ss;
            ss
            << "Print \"[" << scriptName << "] Restoring pre-export SpaceEngine.\"\n"
            << "DisplayMode \"" << preDisplay << "\"\n"
            << "Show " << captureObject << "\n"
            << "Date \"" << preDate << " " << preTime << "\"\n";
            return ss.str();
        };
        // ---------------- BUILD FULL SCRIPT ---------------- //
        std::ostringstream out;
        out << screenshotSetup(initialDate);

        DateParts startParts = PlanetClock::parseParts(initialDate,startTime,planetCalendar.year0);
        double currentTime = planetClock.toSeconds(startParts);

        for (int frame = 1;frame <= frames; ++frame) {
            double nextTime = currentTime;
            if (intervalUnit == "seconds") { //TODO: Refine into a case-switch
                nextTime = planetClock.addSeconds(nextTime,intervalStep);
            } else if (intervalUnit == "hours") {
                nextTime = planetClock.addHours(nextTime,intervalStep);
            } else if (intervalUnit == "days") {
                nextTime = planetClock.addDays(nextTime,intervalStep);
            } else if (intervalUnit == "months") {
                nextTime = planetClock.addMonths(nextTime,intervalStep);
            } else if (intervalUnit == "years") {
                nextTime = planetClock.addYears(nextTime,intervalStep);
            } else {
                throw std::runtime_error("Unknown intervalUnit: " + intervalUnit);
            }

            DateParts currentPart = planetClock.fromSeconds(currentTime);
            DateParts nextPart = planetClock.fromSeconds(nextTime);

            out << frameBlock(
                frame,frames,
                PlanetClock::formatDate(currentPart),
                PlanetClock::formatTime(currentPart),
                PlanetClock::formatDate(nextPart),
                PlanetClock::formatTime(nextPart)
            );

            currentTime = nextTime;
        }
        out << restore();

        // ------------------ WRITE TO FILE ------------------ //
        std::ofstream file(outPath,std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open output: " + outPath);
        }
        file << out.str();
        file.close();

        if (!debugDir.empty()) {
            fs::create_directories(debugDir);
            fs::path outP(outPath);
            std::string stem = outP.stem().string();
            fs:: path txtPath = fs::path(debugDir) / (stem + ".txt");
        }

        std::printf("[LIVE SKYBOXES] Saved %s\n",outPath.c_str());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr,"ERROR: %s\n",e.what());
        return 1;
    }
} // END OF MAIN PROGRAM