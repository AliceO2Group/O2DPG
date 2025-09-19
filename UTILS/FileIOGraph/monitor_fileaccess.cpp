#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/fanotify.h>
#include <sys/stat.h>
#include <sys/types.h>
#define CHK(expr, errcode) \
  if ((expr) == errcode)   \
  perror(#expr), exit(EXIT_FAILURE)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unordered_map>
#include <sstream>
#include <iostream>

#define MAXBUF (BUFSIZ * 2)

int getppid(int pid)
{
  int ppid;
  char buf[MAXBUF];
  char procname[32]; // Holds /proc/4294967296/status\0
  FILE* fp;

  snprintf(procname, sizeof(procname), "/proc/%u/status", pid);
  fp = fopen(procname, "r");
  if (fp != NULL) {
    size_t ret = fread(buf, sizeof(char), MAXBUF - 1, fp);
    if (!ret) {
      return 0;
    } else {
      buf[ret++] = '\0'; // Terminate it.
    }
    fclose(fp);
  }
  char* ppid_loc = strstr(buf, "\nPPid:");
  if (ppid_loc) {
    int ret = sscanf(ppid_loc, "\nPPid:%d", &ppid);
    if (!ret || ret == EOF) {
      return 0;
    }
    return ppid;
  } else {
    return 0;
  }
}

std::string getcmd(pid_t pid)
{
  char path[1024];
  snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);
  if (pid == 0 || pid == 1) {
    return std::string("");
  }

  FILE* file = fopen(path, "r");
  if (file) {
    char buffer[1024]; // max 1024 chars
    size_t bytesRead = fread(buffer, 1, sizeof(buffer), file);
    fclose(file);
    for (int byte = 0; byte < bytesRead; ++byte) {
      if (buffer[byte] == '\0') {
        buffer[byte] = '@';
      }
    }
    return std::string(buffer);
  }
  return std::string("");
}

std::unordered_map<int, bool> good_pid;

bool is_good_pid(int pid, int maxparent)
{
  auto iter = good_pid.find(pid);
  if (iter != good_pid.end()) {
    // the result is known
    return iter->second;
  }
  // the result is not known ---> determine it

  // this means determining the whole chain of parent ids
  if (pid == maxparent) {
    good_pid[pid] = true;
  } else if (pid == 0) {
    good_pid[pid] = false;
  } else {
    good_pid[pid] = is_good_pid(getppid(pid), maxparent);
  }
  return good_pid[pid];
}

int main(int argc, char** argv)
{
  int fan;
  char buf[4096];
  char fdpath[64];
  char path[PATH_MAX + 1];
  ssize_t buflen, linklen;
  struct fanotify_event_metadata* metadata;

  CHK(fan = fanotify_init(FAN_CLASS_NOTIF, O_RDONLY), -1);
  CHK(fanotify_mark(fan, FAN_MARK_ADD | FAN_MARK_MOUNT,
                    FAN_CLOSE_WRITE | FAN_CLOSE_NOWRITE | FAN_EVENT_ON_CHILD, AT_FDCWD, "/"),
      -1);

  std::unordered_map<int, std::string> pid_to_parents; // mapping of a process id to the whole string of parent pids, separated by ';'
  std::unordered_map<int, std::string> pid_to_command; // mapping of a process id to a command

  auto MAX_MOTHER_PID_ENV = getenv("MAXMOTHERPID");
  int max_mother_pid = 1; // everything
  if (MAX_MOTHER_PID_ENV != nullptr) {
    std::cerr << "found env variable MAX_MOTHER_PID_ENV";
    max_mother_pid = std::atoi(MAX_MOTHER_PID_ENV);
    std::cerr << "Setting topmost mother process to " << max_mother_pid << "\n";
  } else {
    std::cerr << "No environment given. Monitoring globally.\n";
  }

  auto thispid = getpid();
  std::string* parentspid = nullptr;

  for (;;) {
    CHK(buflen = read(fan, buf, sizeof(buf)), -1);
    metadata = (struct fanotify_event_metadata*)&buf;
    while (FAN_EVENT_OK(metadata, buflen)) {
      if (metadata->mask & FAN_Q_OVERFLOW) {
        printf("Queue overflow!\n");
        continue;
      }
      sprintf(fdpath, "/proc/self/fd/%d", metadata->fd);
      CHK(linklen = readlink(fdpath, path, sizeof(path) - 1), -1);
      path[linklen] = '\0';
      auto pid = metadata->pid;

      bool record = true;

      // no need to monitor ourselfs
      record = record && pid != thispid;

      // check if we have the right events before continuing
      record = record && (((metadata->mask & FAN_CLOSE_WRITE) || (metadata->mask & FAN_CLOSE_NOWRITE)));

      // check if we have the right pid before continuing
      record = record && is_good_pid(pid, max_mother_pid);

      if (record) {
        auto iter = pid_to_parents.find((int)pid);
        if (iter != pid_to_parents.end()) {
          parentspid = &iter->second;
        } else {
          std::stringstream str;
          // get chain of parent pids
          auto current = (int)pid;
          str << current;
          while (current != max_mother_pid && current != 0) {
            // record command line of current if not already cached
            if (pid_to_command.find((int)current) == pid_to_command.end()) {
              std::string cmd{getcmd(current)};
              pid_to_command[current] = cmd;
              printf("pid-to-command:%i:%s\n", current, cmd.c_str());
            }

            auto next = getppid(current);
            current = next;
            str << ";" << current;
          }
          pid_to_parents[(int)pid] = str.str();
          parentspid = &pid_to_parents[(int)pid];
        }

        if (metadata->mask & FAN_CLOSE_WRITE) {
          printf("\"%s\",write,%s\n", path, parentspid->c_str());
        }
        if (metadata->mask & FAN_CLOSE_NOWRITE) {
          printf("\"%s\",read,%s\n", path, parentspid->c_str());
        }
      }

      close(metadata->fd);
      metadata = FAN_EVENT_NEXT(metadata, buflen);
    }
  }
}
