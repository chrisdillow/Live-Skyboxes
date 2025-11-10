//Cylindrical Panoramic to Stereographically Projected Hemispheres
//Engine
//Chris D. | Version 1 | Version Date: 11/8/2025

// ============================================================== //
// |                      VERSION HISTORY                       | //
// ============================================================== //
//  Version 0 (11/3/2025): Functional launch
//  Version 1 (11/8/2025): Updated two possible k-values in the
//      defintiion of parseArguments() to reflect UI update and more
//      concise, descriptive naming.
//      Modified export file names to match clarity.

// ============================================================== //
// |                     COMPILE BASH SCRIPT                    | //
// ============================================================== //
// g++ stereographicProjectionEngine.cpp -o stereographicProjectionEngine -std=c++17 -O2 -Wall

// ============================================================== //
// |                      INCLUDE / DEFINE                      | //
// ============================================================== //

#define STB_IMAGE_IMPLEMENTATION
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#include "stb_image.h"
#include "stb_image_write.h"

#ifdef USE_OMP
#include <omp.h>
#endif

using namespace std;

static const std::string kScriptName = "CHRIS'S KIT";

// ============================================================== //
// |                         IMAGE I/O                          | //
// ============================================================== //
struct Image {
    int width = 0, height = 0, channels = 0; // channels=3 (RGB)
    std::vector<float> data;                 // height * width * 3, [0..1]
};

static inline float deg2rad(float degrees) { return degrees * float(M_PI) / 180.f; }
static inline float wrapPi(float angle) {
    float twoPi = 2.f * float(M_PI);
    angle = std::fmod(angle + float(M_PI), twoPi);
    if (angle < 0) angle += twoPi;
    return angle - float(M_PI);
}

static Image loadEquirect(const char* path) {
    int width,height,imageContainer;
    stbi_uc* pix = stbi_load(path,&width,&height,&imageContainer, 3);
    if (!pix) throw std::runtime_error("[" + kScriptName + "]: Failed to load: " + std::string(path));
    if (width != 2*height) {
        std::fprintf(stderr,
            "[%s] Warning: input is %dx%d (aspect %.3f), not 2:1. "
            "Proceeding; latitude/longitude will be sampled assuming full [-90°,90°] × [-180°,180°].\n",
            kScriptName.c_str(),width,height,(double)width/height);
    }
    Image img; img.width = width; img.height = height; img.channels = 3; img.data.resize((size_t)width*height*3);
    for (size_t i=0; i < img.data.size(); i++) img.data[i] = pix[i] / 255.f;
    stbi_image_free(pix);
    return img;
}

static void savePNG_RGBA(const char* path,int width,int height,const std::vector<float>& rgba) {
    std::vector<unsigned char> out((size_t)width*height*4);
    for (size_t i=0; i < out.size(); i++) {
        float imageBuffer = std::clamp(rgba[i], 0.f, 1.f);
        out[i] = (unsigned char)std::lround(imageBuffer * 255.f);
    }
    if (!stbi_write_png(path,width,height,4,out.data(),width*4)) {
        throw std::runtime_error("[" + kScriptName + "]: Failed to write: " + std::string(path));
    }
}

// ============================================================== //
// |                      BILINEAR SAMPLING                     | //
// ============================================================== //
static inline void sampleEquirect(const Image& img,float longitude,float latitude,float rgb[3]) {
    float width = (float)img.width, height = (float)img.height;
    float x = (longitude + float(M_PI)) / (2.f * float(M_PI)) * width;         // [0,width)
    float y = (float(M_PI)/2.f - latitude) / float(M_PI) * height;            // [0,height)

    int x0 = (int)std::floor(x), y0 = (int)std::floor(y);
    int x1 = (x0 + 1) % img.width;
    int y1 = std::clamp(y0 + 1, 0, img.height - 1);
    x0 = (x0 % img.width + img.width) % img.width;
    y0 = std::clamp(y0, 0, img.height - 1);

    float horizInterp = x - (float)x0, vertInterp = y - (float)y0;
    auto px = [&](int yIndex, int xIndex, int channel){ return img.data[((size_t)yIndex * img.width + xIndex)*3 + channel]; };
    for (int channel=0; channel < 3; channel++) {
        float topLeft = px(y0,x0,channel), topRight = px(y0,x1,channel), bottomLeft = px(y1,x0,channel), bottomRight = px(y1,x1,channel);
        float top = topLeft * (1 - horizInterp) + topRight * horizInterp;
        float bot = bottomLeft * (1 - horizInterp) + bottomRight * horizInterp;
        rgb[channel] = top * (1 - vertInterp) + bot * vertInterp;
    }
}

// ============================================================== //
// |      INVERSE STEREOGRAPHIC TO UNIT SPHERE PROJECTION       | //
// ============================================================== //
static inline void invStereoToXYZ(float normX,float normY,float& x,float& y,float& z) {
    float radiusSquared = normX * normX + normY * normY;
    float denom = 1.f + radiusSquared;
    x = 2.f * normX/denom;
    y = 2.f * normY/denom;
    z = (1.f - radiusSquared)/denom;
}

static inline void xyzToLonLat(float x,float y,float z,float lon0,float& lon,float& lat) {
    lon = std::atan2(y,x);
    lat = std::asin(std::clamp(z,-1.f,1.f));
    lon = wrapPi(lon - lon0);
}

// ============================================================== //
// |                          OPTIONS                           | //
// ============================================================== //
struct Options {
    std::string input;
    int   size = 2048;
    float lon0degrees = 0.f;
    float southLon0OffsetDegrees = 0.f;
    bool  southMirror = true;
    bool  bothHemispheres = true;
};

// ============================================================== //
// |                HEMISPHERICAL DISC GENERATOR                | //
// ============================================================== //
static void makeDisc(const Image& input,int size,float lon0degrees,bool south,bool southMirror,
                    std::vector<float>& rgbaOut) {
    rgbaOut.assign((size_t)size * size * 4,0.f);
    float radius = size * 0.5f;
    float lon0 = deg2rad(lon0degrees);

    #ifdef USE_OMP
    #pragma omp parallel for schedule(static)
    #endif
    for (int yPix=0; yPix < size; yPix++) {
        for (int xPix=0; xPix < size; xPix++) {
            float normX = ((float)xPix - radius)/radius;      // unit circle boundary (equator)
            float normY = (radius - (float)yPix)/radius;      // +Y up
            float radiusSquared = normX * normX + normY * normY;
            if (radiusSquared > 1.f) continue;

            float sphericalX, sphericalY, sphericalZ;
            invStereoToXYZ(normX,normY,sphericalX,sphericalY,sphericalZ);
            if (south) sphericalZ = -sphericalZ;

            float lon, lat;
            xyzToLonLat(sphericalX,sphericalY,sphericalZ,lon0,lon,lat);

            float rgb[3];
            sampleEquirect(input,lon,lat,rgb);

            int xOut = xPix, yOut = yPix;
            if (south && southMirror) xOut = size - 1 - xPix;

            size_t idx = ((size_t)yOut * size + xOut) * 4;
            rgbaOut[idx+0] = rgb[0];
            rgbaOut[idx+1] = rgb[1];
            rgbaOut[idx+2] = rgb[2];
            rgbaOut[idx+3] = 1.f;
        }
    }
}

// ============================================================== //
// |             SIDE-BY-SIDE HEMISPHERE COMPOSITOR             | //
// ============================================================== //
static void compositeDblHemispheres(const std::vector<float>& north,const std::vector<float>& south,int size,
                       const std::string& outPath) {
    int pad = (int)std::lround(size * 0.05);
    int compWidth = size * 2 + pad * 3;
    int compHeight = size + pad * 2;
    std::vector<float> canvas((size_t)compWidth * compHeight* 4,0.f);

    auto blit = [&](const std::vector<float>& src,int outXoffset,int outYoffset){
        for (int y=0; y < size; y++) {
            for (int x=0; x < size; x++) {
                size_t srcIndex = ((size_t)y*size + x)*4;
                size_t destinationIndex = ((size_t)(outYoffset + y) * compWidth + (outXoffset + x))*4;
                float alpha = src[srcIndex + 3];
                // simple over onto transparent
                for (int channel=0; channel < 3; channel++) canvas[destinationIndex + channel] = src[srcIndex + channel] * alpha + canvas[destinationIndex + channel] * (1.f - alpha);
                canvas[destinationIndex + 3] = alpha + canvas[destinationIndex + 3] * (1.f - alpha);
            }
        }
    };

    blit(north,pad,pad);
    blit(south,pad * 2 + size,pad);
    savePNG_RGBA(outPath.c_str(),compWidth,compHeight,canvas);
}

// ============================================================== //
// |                        CLI PARSING                         | //
// ============================================================== //
static Options parseArguments(int argc,char** argv) {
    Options opt;
    if (argc < 2) {
        std::fprintf(stderr,
            "Usage: %s <input> [--size N] [--lon0 deg] [--southLon0Offset deg] [--southMirror 0|1] [--bothHemispheres 0|1]\n",
            argv[0]);
        std::exit(1);
    }
    opt.input = argv[1];
    for (int i=2; i< argc; i++) {
        std::string key = argv[i];
        auto need = [&](bool has) { if (!has) throw std::runtime_error("[" + kScriptName + "]: Missing value for " + key); };
        if (key == "--size") { need(i + 1 < argc); opt.size = std::stoi(argv[++i]); }
        else if (key == "--lon0") { need(i + 1 < argc); opt.lon0degrees = std::stof(argv[++i]); }
        else if (key == "--southOffset") { need(i + 1 < argc); opt.southLon0OffsetDegrees = std::stof(argv[++i]); }
        else if (key == "--southMirror") { need(i + 1 < argc); opt.southMirror = (std::stoi(argv[++i]) != 0); }
        else if (key == "--bothHemispheres") { need(i + 1 < argc); opt.bothHemispheres = (std::stoi(argv[++i]) != 0); }
        else { std::fprintf(stderr,"Unknown arg: %s\n",key.c_str()); std::exit(1); }
    }
    return opt;
}

// ============================================================== //
// |                        MAIN PROGRAM                        | //
// ============================================================== //
int main(int argc,char** argv) {
    try {
        Options opt = parseArguments(argc,argv);
        Image inputImage = loadEquirect(opt.input.c_str());

        std::vector<float> northRGBA, southRGBA;
        makeDisc(inputImage,opt.size,opt.lon0degrees,/*south=*/false,opt.southMirror,northRGBA);
        makeDisc(inputImage,opt.size,opt.lon0degrees + opt.southLon0OffsetDegrees,
                /*south=*/true,opt.southMirror,southRGBA);

        std::string stem = opt.input;
        auto dot = stem.find_last_of('.');
        if (dot != std::string::npos) stem = stem.substr(0,dot);

        std::string northPath = stem + "_stereoNorth.png";
        std::string southPath = stem + "_stereoSouth.png";
        savePNG_RGBA(northPath.c_str(),opt.size,opt.size,northRGBA);
        savePNG_RGBA(southPath.c_str(),opt.size,opt.size,southRGBA);

        if (opt.bothHemispheres) {
            std::string dbl = stem + "_stereoHemispheres.png";
            compositeDblHemispheres(northRGBA,southRGBA,opt.size,dbl);
        }

        std::printf("Wrote: %s\n",northPath.c_str());
        std::printf("Wrote: %s\n",southPath.c_str());
        if (opt.bothHemispheres) std::printf("Wrote: %s\n",(stem + "_stereoHemispheres.png").c_str());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr,"Error: %s\n",e.what());
        return 1;
    }
} // END OF MAIN PROGRAM