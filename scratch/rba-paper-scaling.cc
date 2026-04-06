#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("RbaPaperScaling");

namespace
{

struct ScenarioConfig
{
    uint32_t numVehicles{100};
    uint32_t numRsus{4};
    double roadLengthM{3000.0};
    uint32_t laneCount{4};
    double laneSpacingM{4.0};
    double rsuOffsetM{10.0};
    double minSpeedMps{15.0};
    double maxSpeedMps{20.0};
    double positionJitterM{2.0};
    double coverageRangeM{300.0};
    double txPowerDbm{20.0};
    Time warmupTime{Seconds(1.0)};
    Time activeTime{Seconds(4.0)};
    Time cleanupTime{Seconds(5.0)};
    Time beaconInterval{MilliSeconds(100)};
    uint32_t packetSizeBytes{134};
    uint32_t pseudonymPayloadBytes{66};
    uint32_t proofPayloadBytes{34};
    uint32_t timestampPayloadBytes{2};
    uint32_t signaturePayloadBytes{32};
    std::string phyMode{"OfdmRate6MbpsBW10MHz"};
    std::string zkprProofModel{"fiat-shamir-sigma"};
    std::string resultsCsv{"results/rba/rba-scaling-summary.csv"};
    std::string flowMonitorXml{};
    uint32_t seed{12345};
    uint32_t run{1};
    uint16_t basePort{6000};
    double proverProcessingDelayMs{4.467};
    double verifierProcessingDelayMs{5.956};
};

struct AggregateStats
{
    uint64_t txPackets{0};
    uint64_t rxPackets{0};
    uint64_t lostPackets{0};
    double delaySumSeconds{0.0};
    double meanNetworkDelayMs{0.0};
    double meanRbaEndToEndDelayMs{0.0};
    double packetLossRatio{0.0};
    double deliveryRatio{0.0};
    double offeredLoadMbps{0.0};
    uint32_t flowCount{0};
};

struct RunTiming
{
    std::string wallClockStartUtc;
    std::string wallClockEndUtc;
    double wallClockElapsedSeconds{0.0};
};

double
Clamp(double value, double low, double high)
{
    return std::max(low, std::min(value, high));
}

void
EnsureParentDirectory(const std::string& path)
{
    if (path.empty())
    {
        return;
    }

    const auto outputPath = std::filesystem::path(path);
    if (outputPath.has_parent_path())
    {
        std::filesystem::create_directories(outputPath.parent_path());
    }
}

std::string
FormatUtcTimestamp(const std::chrono::system_clock::time_point& timestamp)
{
    const auto timeT = std::chrono::system_clock::to_time_t(timestamp);
    std::tm tmUtc{};
#if defined(_WIN32)
    gmtime_s(&tmUtc, &timeT);
#else
    gmtime_r(&timeT, &tmUtc);
#endif

    const auto milliseconds =
        std::chrono::duration_cast<std::chrono::milliseconds>(timestamp.time_since_epoch()) % 1000;

    std::ostringstream stream;
    stream << std::put_time(&tmUtc, "%Y-%m-%dT%H:%M:%S") << '.' << std::setw(3) << std::setfill('0')
           << milliseconds.count() << 'Z';
    return stream.str();
}

std::vector<double>
BuildRsuPositions(double roadLengthM, uint32_t numRsus)
{
    std::vector<double> positions;
    positions.reserve(numRsus);

    if (numRsus == 0)
    {
        return positions;
    }

    if (numRsus == 1)
    {
        positions.push_back(roadLengthM / 2.0);
        return positions;
    }

    for (uint32_t i = 0; i < numRsus; ++i)
    {
        positions.push_back(static_cast<double>(i) * roadLengthM / static_cast<double>(numRsus - 1));
    }
    return positions;
}

uint32_t
FindNearestRsuIndex(double x, const std::vector<double>& rsuPositions)
{
    double bestDistance = std::numeric_limits<double>::max();
    uint32_t bestIndex = 0;

    for (uint32_t i = 0; i < rsuPositions.size(); ++i)
    {
        const double distance = std::abs(x - rsuPositions[i]);
        if (distance < bestDistance)
        {
            bestDistance = distance;
            bestIndex = i;
        }
    }

    return bestIndex;
}

std::vector<double>
InstallVehicleMobility(const NodeContainer& vehicles, const ScenarioConfig& config)
{
    Ptr<ListPositionAllocator> vehiclePositions = CreateObject<ListPositionAllocator>();
    Ptr<UniformRandomVariable> positionJitter = CreateObject<UniformRandomVariable>();
    positionJitter->SetStream(1);

    std::vector<double> initialPositions;
    initialPositions.reserve(config.numVehicles);

    const double halfJitter = config.positionJitterM;
    for (uint32_t i = 0; i < config.numVehicles; ++i)
    {
        const double laneY = static_cast<double>(i % config.laneCount) * config.laneSpacingM;
        const double nominalX =
            config.roadLengthM * (static_cast<double>(i) + 0.5) / static_cast<double>(config.numVehicles);
        const double jitter = positionJitter->GetValue(-halfJitter, halfJitter);
        const double x = Clamp(nominalX + jitter, 0.0, config.roadLengthM);

        vehiclePositions->Add(Vector(x, laneY, 0.0));
        initialPositions.push_back(x);
    }

    MobilityHelper mobility;
    mobility.SetPositionAllocator(vehiclePositions);
    mobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    mobility.Install(vehicles);

    Ptr<UniformRandomVariable> speedRv = CreateObject<UniformRandomVariable>();
    speedRv->SetStream(2);

    for (uint32_t i = 0; i < config.numVehicles; ++i)
    {
        const double speed = speedRv->GetValue(config.minSpeedMps, config.maxSpeedMps);
        auto mobilityModel = vehicles.Get(i)->GetObject<ConstantVelocityMobilityModel>();
        mobilityModel->SetVelocity(Vector(speed, 0.0, 0.0));
    }

    return initialPositions;
}

void
InstallRsuMobility(const NodeContainer& rsus,
                   const std::vector<double>& rsuPositions,
                   const ScenarioConfig& config)
{
    Ptr<ListPositionAllocator> rsuAllocator = CreateObject<ListPositionAllocator>();

    for (double x : rsuPositions)
    {
        rsuAllocator->Add(Vector(x, -config.rsuOffsetM, 0.0));
    }

    MobilityHelper mobility;
    mobility.SetPositionAllocator(rsuAllocator);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(rsus);
}

AggregateStats
CollectFlowMonitorStats(FlowMonitorHelper& flowHelper, Ptr<FlowMonitor> monitor, const ScenarioConfig& config)
{
    AggregateStats stats;

    monitor->CheckForLostPackets();
    auto classifier = DynamicCast<Ipv4FlowClassifier>(flowHelper.GetClassifier());
    const auto flowStats = monitor->GetFlowStats();

    for (const auto& [flowId, flow] : flowStats)
    {
        const auto tuple = classifier->FindFlow(flowId);
        if (tuple.protocol != 17)
        {
            continue;
        }

        if (tuple.destinationPort < config.basePort ||
            tuple.destinationPort >= config.basePort + config.numRsus)
        {
            continue;
        }

        stats.flowCount++;
        stats.txPackets += flow.txPackets;
        stats.rxPackets += flow.rxPackets;
        stats.delaySumSeconds += flow.delaySum.GetSeconds();
    }

    stats.lostPackets = stats.txPackets - stats.rxPackets;
    if (stats.rxPackets > 0)
    {
        stats.meanNetworkDelayMs = (stats.delaySumSeconds * 1000.0) / static_cast<double>(stats.rxPackets);
    }

    stats.meanRbaEndToEndDelayMs =
        stats.meanNetworkDelayMs + config.proverProcessingDelayMs + config.verifierProcessingDelayMs;

    if (stats.txPackets > 0)
    {
        stats.packetLossRatio =
            static_cast<double>(stats.lostPackets) / static_cast<double>(stats.txPackets);
        stats.deliveryRatio =
            static_cast<double>(stats.rxPackets) / static_cast<double>(stats.txPackets);
    }

    const double activeSeconds = config.activeTime.GetSeconds();
    if (activeSeconds > 0.0)
    {
        stats.offeredLoadMbps =
            static_cast<double>(stats.txPackets) * static_cast<double>(config.packetSizeBytes) * 8.0 /
            activeSeconds / 1e6;
    }

    return stats;
}

void
AppendResultsCsv(const ScenarioConfig& config, const AggregateStats& stats, const RunTiming& timing)
{
    EnsureParentDirectory(config.resultsCsv);

    const bool writeHeader = !std::filesystem::exists(config.resultsCsv);
    std::ofstream output(config.resultsCsv, std::ios::app);
    output << std::fixed << std::setprecision(6);

    if (writeHeader)
    {
        output << "seed,run,num_vehicles,num_rsus,total_nodes,road_length_m,lane_count,lane_spacing_m,"
               << "coverage_range_m,tx_power_dbm,packet_size_bytes,pseudonym_payload_bytes,"
               << "proof_payload_bytes,timestamp_payload_bytes,signature_payload_bytes,"
               << "beacon_interval_ms,warmup_s,active_s,cleanup_s,phy_mode,zkpr_proof_model,"
               << "prover_processing_delay_ms,verifier_processing_delay_ms,"
               << "flow_count,tx_packets,rx_packets,lost_packets,delivery_ratio,packet_loss_ratio,"
               << "offered_load_mbps,mean_network_delay_ms,mean_rba_end_to_end_delay_ms,"
               << "wall_clock_start_utc,wall_clock_end_utc,wall_clock_elapsed_s\n";
    }

    output << config.seed << ',' << config.run << ',' << config.numVehicles << ',' << config.numRsus
           << ',' << (config.numVehicles + config.numRsus) << ',' << config.roadLengthM << ','
           << config.laneCount << ',' << config.laneSpacingM << ',' << config.coverageRangeM << ','
           << config.txPowerDbm << ',' << config.packetSizeBytes << ','
           << config.pseudonymPayloadBytes << ',' << config.proofPayloadBytes << ','
           << config.timestampPayloadBytes << ',' << config.signaturePayloadBytes << ','
           << config.beaconInterval.GetMilliSeconds() << ',' << config.warmupTime.GetSeconds() << ','
           << config.activeTime.GetSeconds() << ',' << config.cleanupTime.GetSeconds() << ','
           << config.phyMode << ',' << config.zkprProofModel << ',' << config.proverProcessingDelayMs
           << ',' << config.verifierProcessingDelayMs
           << ',' << stats.flowCount << ',' << stats.txPackets << ',' << stats.rxPackets << ','
           << stats.lostPackets << ',' << stats.deliveryRatio << ',' << stats.packetLossRatio << ','
           << stats.offeredLoadMbps << ',' << stats.meanNetworkDelayMs << ','
           << stats.meanRbaEndToEndDelayMs << ',' << timing.wallClockStartUtc << ','
           << timing.wallClockEndUtc << ',' << timing.wallClockElapsedSeconds << '\n';
}

} // namespace

int
main(int argc, char* argv[])
{
    ScenarioConfig config;

    CommandLine cmd(__FILE__);
    cmd.AddValue("numVehicles", "Number of vehicles to simulate", config.numVehicles);
    cmd.AddValue("numRsus", "Number of roadside units (RSUs)", config.numRsus);
    cmd.AddValue("roadLength", "Highway length in meters", config.roadLengthM);
    cmd.AddValue("laneCount", "Number of highway lanes", config.laneCount);
    cmd.AddValue("laneSpacing", "Distance between lanes in meters", config.laneSpacingM);
    cmd.AddValue("rsuOffset", "RSU offset from the first lane in meters", config.rsuOffsetM);
    cmd.AddValue("minSpeed", "Minimum vehicle speed in m/s", config.minSpeedMps);
    cmd.AddValue("maxSpeed", "Maximum vehicle speed in m/s", config.maxSpeedMps);
    cmd.AddValue("positionJitter", "Per-vehicle position jitter in meters", config.positionJitterM);
    cmd.AddValue("coverageRange", "Deterministic communication radius in meters", config.coverageRangeM);
    cmd.AddValue("txPower", "Transmit power in dBm", config.txPowerDbm);
    cmd.AddValue("warmupTime", "Warm-up time before traffic starts", config.warmupTime);
    cmd.AddValue("activeTime", "Traffic generation time window", config.activeTime);
    cmd.AddValue("cleanupTime", "Cleanup time after traffic stops", config.cleanupTime);
    cmd.AddValue("beaconInterval", "Interval between authenticated packets", config.beaconInterval);
    cmd.AddValue("packetSize", "Authenticated packet size in bytes", config.packetSizeBytes);
    cmd.AddValue("pseudonymPayloadBytes",
                 "Combined size of the two compressed pseudo-identities in bytes",
                 config.pseudonymPayloadBytes);
    cmd.AddValue("proofPayloadBytes",
                 "Compressed Sigma-style ZKPR transcript size in bytes",
                 config.proofPayloadBytes);
    cmd.AddValue("timestampPayloadBytes",
                 "Freshness timestamp size in bytes",
                 config.timestampPayloadBytes);
    cmd.AddValue("signaturePayloadBytes",
                 "Compact ECC signature size in bytes",
                 config.signaturePayloadBytes);
    cmd.AddValue("phyMode", "802.11p PHY mode", config.phyMode);
    cmd.AddValue("zkprProofModel", "Logical proof model carried by each authenticated packet", config.zkprProofModel);
    cmd.AddValue("resultsCsv", "CSV file to append aggregated results to", config.resultsCsv);
    cmd.AddValue("flowMonitorXml", "Optional FlowMonitor XML output path", config.flowMonitorXml);
    cmd.AddValue("seed", "ns-3 global random seed", config.seed);
    cmd.AddValue("run", "ns-3 run number", config.run);
    cmd.AddValue("basePort", "Base UDP destination port", config.basePort);
    cmd.AddValue("proverProcessingDelayMs",
                 "Per-packet prover processing delay in milliseconds",
                 config.proverProcessingDelayMs);
    cmd.AddValue("verifierProcessingDelayMs",
                 "Per-packet verifier processing delay in milliseconds",
                 config.verifierProcessingDelayMs);
    cmd.Parse(argc, argv);

    const auto wallClockStart = std::chrono::system_clock::now();
    const auto monotonicStart = std::chrono::steady_clock::now();

    if (config.numVehicles == 0 || config.numRsus == 0)
    {
        NS_FATAL_ERROR("numVehicles and numRsus must both be greater than zero");
    }

    if (config.minSpeedMps > config.maxSpeedMps)
    {
        NS_FATAL_ERROR("minSpeed must be less than or equal to maxSpeed");
    }

    RngSeedManager::SetSeed(config.seed);
    RngSeedManager::SetRun(config.run);

    Config::SetDefault("ns3::WifiRemoteStationManager::NonUnicastMode", StringValue(config.phyMode));

    NodeContainer vehicles;
    vehicles.Create(config.numVehicles);

    NodeContainer rsus;
    rsus.Create(config.numRsus);

    NodeContainer allNodes;
    allNodes.Add(vehicles);
    allNodes.Add(rsus);

    const std::vector<double> rsuPositions = BuildRsuPositions(config.roadLengthM, config.numRsus);
    const std::vector<double> vehiclePositions = InstallVehicleMobility(vehicles, config);
    InstallRsuMobility(rsus, rsuPositions, config);

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211p);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue(config.phyMode),
                                 "ControlMode",
                                 StringValue(config.phyMode));

    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::RangePropagationLossModel",
                               "MaxRange",
                               DoubleValue(config.coverageRangeM));

    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    phy.Set("TxPowerStart", DoubleValue(config.txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(config.txPowerDbm));

    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");

    NetDeviceContainer devices = wifi.Install(phy, mac, allNodes);

    InternetStackHelper internet;
    internet.Install(allNodes);

    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.42.0.0", "255.255.0.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(devices);

    std::vector<Ipv4Address> rsuAddresses;
    rsuAddresses.reserve(config.numRsus);
    for (uint32_t i = 0; i < config.numRsus; ++i)
    {
        rsuAddresses.push_back(interfaces.GetAddress(config.numVehicles + i));
    }

    ApplicationContainer sinkApps;
    for (uint32_t i = 0; i < config.numRsus; ++i)
    {
        UdpServerHelper server(config.basePort + i);
        sinkApps.Add(server.Install(rsus.Get(i)));
    }

    sinkApps.Start(Seconds(0.0));
    sinkApps.Stop(config.warmupTime + config.activeTime + config.cleanupTime);

    Ptr<UniformRandomVariable> startJitter = CreateObject<UniformRandomVariable>();
    startJitter->SetStream(3);

    ApplicationContainer clientApps;
    // The wireless simulation models only the prover -> verifier exchange.
    // TA and blockchain operations remain logical control-plane steps folded into the fixed processing delays.
    for (uint32_t i = 0; i < config.numVehicles; ++i)
    {
        const uint32_t rsuIndex = FindNearestRsuIndex(vehiclePositions[i], rsuPositions);
        UdpClientHelper client(rsuAddresses[rsuIndex], config.basePort + rsuIndex);
        client.SetAttribute("Interval", TimeValue(config.beaconInterval));
        client.SetAttribute("MaxPackets", UintegerValue(0));
        client.SetAttribute("PacketSize", UintegerValue(config.packetSizeBytes));

        ApplicationContainer app = client.Install(vehicles.Get(i));
        const Time startTime =
            config.warmupTime + Seconds(startJitter->GetValue(0.0, config.beaconInterval.GetSeconds()));
        app.Start(startTime);
        app.Stop(config.warmupTime + config.activeTime);
        clientApps.Add(app);
    }

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();

    Simulator::Stop(config.warmupTime + config.activeTime + config.cleanupTime);
    Simulator::Run();

    const AggregateStats stats = CollectFlowMonitorStats(flowHelper, monitor, config);

    if (!config.flowMonitorXml.empty())
    {
        EnsureParentDirectory(config.flowMonitorXml);
        monitor->SerializeToXmlFile(config.flowMonitorXml, true, true);
    }

    const auto wallClockEnd = std::chrono::system_clock::now();
    RunTiming timing;
    timing.wallClockStartUtc = FormatUtcTimestamp(wallClockStart);
    timing.wallClockEndUtc = FormatUtcTimestamp(wallClockEnd);
    timing.wallClockElapsedSeconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - monotonicStart).count();

    AppendResultsCsv(config, stats, timing);

    std::ostringstream summary;
    summary << std::fixed << std::setprecision(6);
    summary << "seed=" << config.seed << " run=" << config.run << " vehicles=" << config.numVehicles
            << " rsus=" << config.numRsus << " txPackets=" << stats.txPackets
            << " rxPackets=" << stats.rxPackets << " lostPackets=" << stats.lostPackets
            << " lossRatio=" << stats.packetLossRatio
            << " meanNetworkDelayMs=" << stats.meanNetworkDelayMs
            << " meanRbaEndToEndDelayMs=" << stats.meanRbaEndToEndDelayMs
            << " wallClockElapsedS=" << timing.wallClockElapsedSeconds
            << " resultsCsv=" << config.resultsCsv;
    std::cout << summary.str() << std::endl;

    Simulator::Destroy();
    return 0;
}
