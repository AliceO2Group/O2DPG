#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/fanotify.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <string.h>
#include <unordered_map>
#include <sstream>
#include <iostream>

#define CHK(expr, errcode) \
  if ((expr) == errcode)   \
  {                        \
    perror(#expr);         \
    exit(EXIT_FAILURE);    \
  }

#define MAXBUF (BUFSIZ * 2)

int getppid_safe(int pid)
{
  int ppid = 0;
  char buf[MAXBUF];
  char procname[64]; // big enough for /proc/<pid>/status
  FILE *fp;

  snprintf(procname, sizeof(procname), "/proc/%d/status", pid);
  fp = fopen(procname, "r");
  if (fp != NULL)
  {
    size_t ret = fread(buf, sizeof(char), MAXBUF - 1, fp);
    if (ret > 0)
      buf[ret] = '\0';
    fclose(fp);
  }
  char *ppid_loc = strstr(buf, "\nPPid:");
  if (ppid_loc)
  {
    if (sscanf(ppid_loc, "\nPPid:%d", &ppid) != 1)
      return 0;
    return ppid;
  }
  return 0;
}

std::string getcmd(pid_t pid)
{
  if (pid == 0 || pid == 1)
    return std::string("");

  char path[64];
  snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);

  FILE *file = fopen(path, "r");
  if (file)
  {
    char buffer[1024]; // max 1k command line
    size_t bytesRead = fread(buffer, 1, sizeof(buffer), file);
    fclose(file);
    for (size_t i = 0; i < bytesRead; ++i)
    {
      if (buffer[i] == '\0')
        buffer[i] = '@';
    }
    return std::string(buffer, bytesRead);
  }
  return std::string("");
}

std::unordered_map<int, bool> good_pid_cache;
std::unordered_map<int, std::string> pid_to_parents;
std::unordered_map<int, std::string> pid_to_command;

bool is_good_pid(int pid, int maxparent)
{
  auto iter = good_pid_cache.find(pid);
  if (iter != good_pid_cache.end())
    return iter->second;

  if (pid == maxparent)
    return good_pid_cache[pid] = true;
  if (pid == 0)
    return good_pid_cache[pid] = false;

  return good_pid_cache[pid] = is_good_pid(getppid_safe(pid), maxparent);
}

std::string build_parent_chain(int pid, int maxparent)
{
  auto iter = pid_to_parents.find(pid);
  if (iter != pid_to_parents.end())
    return iter->second;

  std::stringstream str;
  int current = pid;
  str << current;
  while (current != maxparent && current != 0)
  {
    if (pid_to_command.find(current) == pid_to_command.end())
    {
      std::string cmd = getcmd(current);
      pid_to_command[current] = cmd;
      fprintf(stdout, "pid-to-command:%i:%s\n", current, cmd.c_str());
    }
    int next = getppid_safe(current);
    current = next;
    str << ";" << current;
  }
  pid_to_parents[pid] = str.str();
  return str.str();
}

int main(int argc, char **argv)
{
  int fan;
  char buf[8192];
  char fdpath[64];
  char path[PATH_MAX + 1];
  ssize_t buflen, linklen;
  struct fanotify_event_metadata *metadata;

  // init fanotify

  // with this we can observe specific root directories
  auto ROOT_PATH_ENV = getenv("FILEACCESS_MON_ROOTPATH");
  std::string root_path = "/";
  if (ROOT_PATH_ENV) {
    root_path = std::string(ROOT_PATH_ENV);
    std::cerr << "Observing file access below " << root_path << "\n";
  }

  CHK(fan = fanotify_init(FAN_CLASS_NOTIF, O_RDONLY), -1);
  CHK(fanotify_mark(fan, FAN_MARK_ADD | FAN_MARK_MOUNT,
                    FAN_CLOSE_WRITE | FAN_CLOSE_NOWRITE | FAN_EVENT_ON_CHILD,
                    AT_FDCWD, root_path.c_str()),
      -1);

  // read env for filtering
  auto MAX_MOTHER_PID_ENV = getenv("MAXMOTHERPID");
  int max_mother_pid = 1; // default: allow everything
  if (MAX_MOTHER_PID_ENV != nullptr)
  {
    max_mother_pid = std::atoi(MAX_MOTHER_PID_ENV);
    std::cerr << "Setting topmost mother process to " << max_mother_pid << "\n";
  }
  else
  {
    std::cerr << "No MAXMOTHERPID environment given\n";
  }

  auto thispid = getpid();

  struct pollfd fds[1];
  fds[0].fd = fan;
  fds[0].events = POLLIN;

  for (;;)
  {
    int pollres = poll(fds, 1, -1); // wait indefinitely
    if (pollres == -1)
    {
      perror("poll");
      continue;
    }

    if (fds[0].revents & POLLIN)
    {
      buflen = read(fan, buf, sizeof(buf));
      if (buflen == -1)
      {
        perror("read");
        continue;
      }
      metadata = (struct fanotify_event_metadata *)&buf;
      while (FAN_EVENT_OK(metadata, buflen))
      {
        if (metadata->mask & FAN_Q_OVERFLOW)
        {
          fprintf(stderr, "Queue overflow!\n");
          continue;
        }
        snprintf(fdpath, sizeof(fdpath), "/proc/self/fd/%d", metadata->fd);
        linklen = readlink(fdpath, path, sizeof(path) - 1);
        if (linklen >= 0)
        {
          path[linklen] = '\0';
          int pid = metadata->pid;

          bool record = true;
          record = record && pid != thispid;
          record = record && (metadata->mask & (FAN_CLOSE_WRITE | FAN_CLOSE_NOWRITE));
          record = record && is_good_pid(pid, max_mother_pid);

          if (record)
          {
            std::string parent_chain = build_parent_chain(pid, max_mother_pid);

            if (metadata->mask & FAN_CLOSE_WRITE)
            {
              printf("\"%s\",write,%s\n", path, parent_chain.c_str());
              fflush(stdout);
            }
            if (metadata->mask & FAN_CLOSE_NOWRITE)
            {
              printf("\"%s\",read,%s\n", path, parent_chain.c_str());
              fflush(stdout);
            }
          }
        }
        close(metadata->fd);
        metadata = FAN_EVENT_NEXT(metadata, buflen);
      }
    }
  }
}
