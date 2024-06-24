// A small, standalone code, to quickly record CPU-vs-T
// for a running process, so that one can make plots.
// Simply compile with g++ -O2 monitorCPU.cpp -o monitor.exe and run.

#include <iostream>
#include <fstream>
#include <sstream>
#include <chrono>
#include <thread>
#include <unistd.h>

double getProcessCpuUtilization(int pid)
{
  std::ifstream statFile("/proc/" + std::to_string(pid) + "/stat");
  if (!statFile.is_open()) {
    std::cerr << "Failed to open stat file for PID " << pid << std::endl;
    return -1.0; // Error indicator
  }

  std::string line;
  std::getline(statFile, line);
  statFile.close();

  std::istringstream iss(line);
  std::string token;
  // We only need the 14th and 15th fields: utime and stime
  for (int i = 0; i < 13; ++i) {
    iss >> token;
  }
  unsigned long utime, stime;
  iss >> utime >> stime;

  unsigned long process_total = utime + stime;
  static unsigned long last_process_total = 0;

  // Read total CPU time from /proc/stat
  unsigned long total_cpu_time = 0;
  std::ifstream stat("/proc/stat");
  if (stat.is_open()) {
    std::string cpuLabel;
    while (stat >> cpuLabel && cpuLabel != "cpu") {
      // Skip non-cpu lines
      stat.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    }
    unsigned long value;
    for (int i = 0; i < 10; ++i) {
      stat >> value;
      total_cpu_time += value;
    }
  } else {
    std::cerr << "Failed to open /proc/stat" << std::endl;
    return -1.0; // Error indicator
  }
  stat.close();

  // Calculate CPU utilization over the last 5 seconds
  static unsigned long last_total_cpu_time = total_cpu_time;
  double utilization = (process_total - last_process_total) * 1.0 / (total_cpu_time - last_total_cpu_time);

  // Update last total CPU time for next calculation
  last_total_cpu_time = total_cpu_time;
  last_process_total = process_total;

  return utilization;
}

int getNumberOfCores()
{
  return sysconf(_SC_NPROCESSORS_ONLN);
}

int main(int argc, char* argv[])
{
  int pid = -1;

  if (argc > 1) {
    pid = atoi(argv[1]);
  }

  while (true) {
    double cpuUtilization = getProcessCpuUtilization(pid);
    if (cpuUtilization >= 0.0) {
      std::cerr << "CPU(" << pid << ") " << cpuUtilization * 100 * getNumberOfCores() << "\n";
    } else {
      std::cerr << "Error retrieving CPU utilization." << std::endl;
    }

    // Wait for 2 seconds
    std::this_thread::sleep_for(std::chrono::seconds(2));
  }
  return 0;
}
